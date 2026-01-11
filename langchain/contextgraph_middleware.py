"""
ContextGraph LangChain Middleware (v1+)

Middleware-based integration for LangChain v1+ agents using the new
create_agent() pattern with @before_model, @wrap_tool_call decorators.

Installation:
    pip install contextgraph-langchain

Usage:
    from langchain.agents import create_agent
    from contextgraph_middleware import contextgraph_middleware

    agent = create_agent(
        model="openai:gpt-4o",
        tools=[...],
        middleware=[contextgraph_middleware(
            api_key=os.environ["CG_API_KEY"],
            agent_id="my-agent"
        )]
    )
"""

import os
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Callable, List
from functools import wraps

import httpx

logger = logging.getLogger(__name__)


class ContextGraphClient:
    """HTTP client for ContextGraph API."""

    def __init__(
        self,
        api_key: str,
        agent_id: str,
        api_url: str = "https://contextgraph-api.fly.dev",
        auto_approve: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.api_key = api_key
        self.agent_id = agent_id
        self.api_url = api_url.rstrip("/")
        self.auto_approve = auto_approve
        self.metadata = metadata or {}

        self._client = httpx.Client(
            base_url=self.api_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def log_decision(
        self,
        decision_type: str,
        action: str,
        context: Dict[str, Any],
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
                    "source": "langchain-v1",
                },
            }

            response = self._client.post("/v1/decisions", json=payload)
            response.raise_for_status()

            decision = response.json()
            decision_id = decision.get("id")

            if self.auto_approve and decision_id:
                self.transition_decision(decision_id, "approved")

            return decision_id

        except Exception as e:
            logger.error(f"Failed to log decision to ContextGraph: {e}")
            return None

    def transition_decision(
        self, decision_id: str, status: str, result: Optional[Dict] = None
    ):
        """Transition a decision to a new status."""
        try:
            payload = {"status": status}
            if result:
                payload["result"] = result

            response = self._client.post(
                f"/v1/decisions/{decision_id}/transition", json=payload
            )
            response.raise_for_status()

        except Exception as e:
            logger.error(f"Failed to transition decision {decision_id}: {e}")

    def close(self):
        """Close the HTTP client."""
        self._client.close()


def contextgraph_middleware(
    api_key: Optional[str] = None,
    agent_id: Optional[str] = None,
    api_url: str = "https://contextgraph-api.fly.dev",
    auto_approve: bool = False,
    log_model_calls: bool = True,
    log_tool_calls: bool = True,
    metadata: Optional[Dict[str, Any]] = None,
) -> List[Callable]:
    """
    Create ContextGraph middleware for LangChain v1 agents.

    Returns a list of middleware functions that can be passed to create_agent().

    Args:
        api_key: ContextGraph API key. Defaults to CG_API_KEY env var.
        agent_id: ID of the registered agent. Defaults to CG_AGENT_ID env var.
        api_url: ContextGraph API URL.
        auto_approve: Automatically approve decisions (for testing).
        log_model_calls: Whether to log model calls.
        log_tool_calls: Whether to log tool calls.
        metadata: Additional metadata to include with all decisions.

    Returns:
        List of middleware functions for create_agent().

    Example:
        from langchain.agents import create_agent
        from contextgraph_middleware import contextgraph_middleware

        agent = create_agent(
            model="openai:gpt-4o",
            tools=[search_tool, calculator_tool],
            middleware=contextgraph_middleware(
                api_key=os.environ["CG_API_KEY"],
                agent_id="my-research-agent"
            )
        )
    """
    resolved_api_key = api_key or os.environ.get("CG_API_KEY")
    resolved_agent_id = agent_id or os.environ.get("CG_AGENT_ID")

    if not resolved_api_key:
        raise ValueError(
            "ContextGraph API key required. Set CG_API_KEY env var or pass api_key."
        )
    if not resolved_agent_id:
        raise ValueError(
            "ContextGraph agent ID required. Set CG_AGENT_ID env var or pass agent_id."
        )

    client = ContextGraphClient(
        api_key=resolved_api_key,
        agent_id=resolved_agent_id,
        api_url=api_url,
        auto_approve=auto_approve,
        metadata=metadata,
    )

    # Track active decisions
    active_decisions: Dict[str, str] = {}

    middlewares = []

    if log_model_calls:
        # Import LangChain middleware decorators
        try:
            from langchain.agents.middleware import before_model, after_model

            @before_model
            def log_model_start(state, runtime) -> None:
                """Log model call to ContextGraph."""
                messages = state.get("messages", [])
                decision_id = client.log_decision(
                    decision_type="model_call",
                    action="invoke_model",
                    context={
                        "message_count": len(messages),
                        "last_message": str(messages[-1]) if messages else None,
                    },
                )
                if decision_id:
                    active_decisions["model"] = decision_id

            @after_model
            def log_model_end(state, runtime) -> None:
                """Mark model call as executed."""
                decision_id = active_decisions.pop("model", None)
                if decision_id:
                    messages = state.get("messages", [])
                    client.transition_decision(
                        decision_id,
                        "executed",
                        result={
                            "response": str(messages[-1]) if messages else None,
                        },
                    )

            middlewares.extend([log_model_start, log_model_end])

        except ImportError:
            logger.warning(
                "LangChain v1 middleware not available. "
                "Install langchain>=1.0.0 for middleware support."
            )

    if log_tool_calls:
        try:
            from langchain.agents.middleware import wrap_tool_call

            @wrap_tool_call
            def log_tool_execution(tool_call, state, runtime):
                """Wrap tool calls with ContextGraph logging."""
                tool_name = tool_call.get("name", "unknown_tool")
                tool_input = tool_call.get("args", {})

                # Log decision before tool execution
                decision_id = client.log_decision(
                    decision_type="tool_execution",
                    action=tool_name,
                    context={
                        "tool_name": tool_name,
                        "tool_input": _serialize(tool_input),
                    },
                )

                try:
                    # Execute the tool (yield control back to LangChain)
                    result = yield tool_call

                    # Mark as executed on success
                    if decision_id:
                        client.transition_decision(
                            decision_id,
                            "executed",
                            result={"output": _serialize(result)},
                        )

                    return result

                except Exception as e:
                    # Mark as failed on error
                    if decision_id:
                        client.transition_decision(
                            decision_id,
                            "failed",
                            result={"error": str(e)},
                        )
                    raise

            middlewares.append(log_tool_execution)

        except ImportError:
            logger.warning(
                "LangChain v1 middleware not available. "
                "Install langchain>=1.0.0 for middleware support."
            )

    return middlewares


def _serialize(obj: Any) -> Any:
    """Serialize object for JSON."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(v) for v in obj]
    if hasattr(obj, "dict"):
        return _serialize(obj.dict())
    if hasattr(obj, "__dict__"):
        return _serialize(obj.__dict__)
    return str(obj)


# ============================================================
# Legacy Callback Handler (for LangChain < 1.0 compatibility)
# ============================================================

# Re-export the legacy callback for backwards compatibility
from contextgraph_callback import ContextGraphCallback

__all__ = ["contextgraph_middleware", "ContextGraphCallback", "ContextGraphClient"]
