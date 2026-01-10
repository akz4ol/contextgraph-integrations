"""
ContextGraph LangChain Callback Handler

Automatically logs all LangChain agent decisions to ContextGraph Cloud
for audit trails, policy enforcement, and compliance reporting.

Installation:
    pip install contextgraph-langchain

Usage:
    from contextgraph_langchain import ContextGraphCallback

    callback = ContextGraphCallback(
        api_key=os.environ["CG_API_KEY"],
        agent_id="my-langchain-agent"
    )

    agent = AgentExecutor(
        agent=agent,
        tools=tools,
        callbacks=[callback]
    )
"""

import os
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

import httpx
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)


class ContextGraphCallback(BaseCallbackHandler):
    """
    LangChain callback handler that logs decisions to ContextGraph Cloud.

    This handler captures:
    - Tool invocations as decisions
    - Agent actions with reasoning
    - Chain executions
    - LLM calls (optional)

    Each captured event is logged with full context for audit trails.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        agent_id: Optional[str] = None,
        api_url: str = "https://contextgraph-api.fly.dev",
        log_llm_calls: bool = False,
        log_chain_calls: bool = True,
        auto_approve: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the ContextGraph callback handler.

        Args:
            api_key: ContextGraph API key. Defaults to CG_API_KEY env var.
            agent_id: ID of the registered agent. Defaults to CG_AGENT_ID env var.
            api_url: ContextGraph API URL.
            log_llm_calls: Whether to log individual LLM calls.
            log_chain_calls: Whether to log chain executions.
            auto_approve: Automatically approve decisions (for testing).
            metadata: Additional metadata to include with all decisions.
        """
        super().__init__()

        self.api_key = api_key or os.environ.get("CG_API_KEY")
        self.agent_id = agent_id or os.environ.get("CG_AGENT_ID")
        self.api_url = api_url.rstrip("/")
        self.log_llm_calls = log_llm_calls
        self.log_chain_calls = log_chain_calls
        self.auto_approve = auto_approve
        self.metadata = metadata or {}

        if not self.api_key:
            raise ValueError(
                "ContextGraph API key required. Set CG_API_KEY env var or pass api_key."
            )
        if not self.agent_id:
            raise ValueError(
                "ContextGraph agent ID required. Set CG_AGENT_ID env var or pass agent_id."
            )

        self._client = httpx.Client(
            base_url=self.api_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

        # Track active runs
        self._run_decisions: Dict[str, str] = {}

    def _log_decision(
        self,
        decision_type: str,
        action: str,
        context: Dict[str, Any],
        run_id: Optional[str] = None,
    ) -> Optional[str]:
        """Log a decision to ContextGraph."""
        try:
            payload = {
                "agent_id": self.agent_id,
                "type": decision_type,
                "action": action,
                "status": "proposed",
                "context": {
                    **context,
                    **self.metadata,
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "langchain",
                },
            }

            if run_id:
                payload["context"]["run_id"] = run_id

            response = self._client.post("/v1/decisions", json=payload)
            response.raise_for_status()

            decision = response.json()
            decision_id = decision.get("id")

            if self.auto_approve and decision_id:
                self._transition_decision(decision_id, "approved")

            return decision_id

        except Exception as e:
            logger.error(f"Failed to log decision to ContextGraph: {e}")
            return None

    def _transition_decision(self, decision_id: str, status: str, result: Optional[Dict] = None):
        """Transition a decision to a new status."""
        try:
            payload = {"status": status}
            if result:
                payload["result"] = result

            response = self._client.post(
                f"/v1/decisions/{decision_id}/transition",
                json=payload
            )
            response.raise_for_status()

        except Exception as e:
            logger.error(f"Failed to transition decision {decision_id}: {e}")

    # ==================== Agent Callbacks ====================

    def on_agent_action(
        self,
        action: AgentAction,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Log agent tool invocation as a decision."""
        decision_id = self._log_decision(
            decision_type="tool_invocation",
            action=action.tool,
            context={
                "tool": action.tool,
                "tool_input": self._serialize(action.tool_input),
                "reasoning": action.log,
            },
            run_id=str(run_id),
        )

        if decision_id:
            self._run_decisions[str(run_id)] = decision_id

    def on_agent_finish(
        self,
        finish: AgentFinish,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Mark agent decision as executed."""
        decision_id = self._run_decisions.pop(str(run_id), None)

        if decision_id:
            self._transition_decision(
                decision_id,
                "executed",
                result={
                    "output": self._serialize(finish.return_values),
                    "log": finish.log,
                },
            )

    # ==================== Tool Callbacks ====================

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        inputs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Log tool execution start."""
        tool_name = serialized.get("name", "unknown_tool")

        decision_id = self._log_decision(
            decision_type="tool_execution",
            action=tool_name,
            context={
                "tool": tool_name,
                "input": input_str,
                "inputs": self._serialize(inputs),
                "tags": tags,
                "metadata": metadata,
            },
            run_id=str(run_id),
        )

        if decision_id:
            self._run_decisions[str(run_id)] = decision_id

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Mark tool execution as completed."""
        decision_id = self._run_decisions.pop(str(run_id), None)

        if decision_id:
            self._transition_decision(
                decision_id,
                "executed",
                result={"output": output},
            )

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Mark tool execution as failed."""
        decision_id = self._run_decisions.pop(str(run_id), None)

        if decision_id:
            self._transition_decision(
                decision_id,
                "failed",
                result={"error": str(error)},
            )

    # ==================== Chain Callbacks ====================

    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Log chain execution start."""
        if not self.log_chain_calls:
            return

        chain_name = serialized.get("name", serialized.get("id", ["unknown"])[-1])

        decision_id = self._log_decision(
            decision_type="chain_execution",
            action=chain_name,
            context={
                "chain": chain_name,
                "inputs": self._serialize(inputs),
                "tags": tags,
                "metadata": metadata,
            },
            run_id=str(run_id),
        )

        if decision_id:
            self._run_decisions[str(run_id)] = decision_id

    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Mark chain execution as completed."""
        if not self.log_chain_calls:
            return

        decision_id = self._run_decisions.pop(str(run_id), None)

        if decision_id:
            self._transition_decision(
                decision_id,
                "executed",
                result={"outputs": self._serialize(outputs)},
            )

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Mark chain execution as failed."""
        if not self.log_chain_calls:
            return

        decision_id = self._run_decisions.pop(str(run_id), None)

        if decision_id:
            self._transition_decision(
                decision_id,
                "failed",
                result={"error": str(error)},
            )

    # ==================== LLM Callbacks ====================

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Log LLM call start."""
        if not self.log_llm_calls:
            return

        model_name = serialized.get("name", "unknown_model")

        decision_id = self._log_decision(
            decision_type="llm_call",
            action=model_name,
            context={
                "model": model_name,
                "prompts": prompts,
                "tags": tags,
                "metadata": metadata,
            },
            run_id=str(run_id),
        )

        if decision_id:
            self._run_decisions[str(run_id)] = decision_id

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Mark LLM call as completed."""
        if not self.log_llm_calls:
            return

        decision_id = self._run_decisions.pop(str(run_id), None)

        if decision_id:
            self._transition_decision(
                decision_id,
                "executed",
                result={
                    "generations": [
                        [g.text for g in gen] for gen in response.generations
                    ],
                    "llm_output": response.llm_output,
                },
            )

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Mark LLM call as failed."""
        if not self.log_llm_calls:
            return

        decision_id = self._run_decisions.pop(str(run_id), None)

        if decision_id:
            self._transition_decision(
                decision_id,
                "failed",
                result={"error": str(error)},
            )

    # ==================== Utilities ====================

    def _serialize(self, obj: Any) -> Any:
        """Serialize object for JSON."""
        if obj is None:
            return None
        if isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, dict):
            return {k: self._serialize(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._serialize(v) for v in obj]
        if hasattr(obj, "dict"):
            return self._serialize(obj.dict())
        if hasattr(obj, "__dict__"):
            return self._serialize(obj.__dict__)
        return str(obj)

    def __del__(self):
        """Cleanup HTTP client."""
        if hasattr(self, "_client"):
            self._client.close()
