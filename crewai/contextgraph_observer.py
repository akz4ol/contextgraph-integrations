"""
ContextGraph CrewAI Observer

Automatically logs all CrewAI crew and agent decisions to ContextGraph Cloud
for audit trails, policy enforcement, and compliance reporting.

Installation:
    pip install contextgraph-crewai

Usage:
    from contextgraph_crewai import ContextGraphObserver

    observer = ContextGraphObserver(
        api_key=os.environ["CG_API_KEY"],
        crew_id="my-crew"
    )

    crew = Crew(
        agents=[agent1, agent2],
        tasks=[task1, task2],
        callbacks=[observer]
    )
"""

import os
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class TaskEvent:
    """Represents a CrewAI task event."""
    task_id: str
    agent_name: str
    task_description: str
    status: str
    output: Optional[str] = None
    error: Optional[str] = None


class ContextGraphObserver:
    """
    CrewAI callback observer that logs decisions to ContextGraph Cloud.

    This observer captures:
    - Task assignments
    - Agent actions
    - Tool usage
    - Task completions
    - Crew execution flow

    Each captured event is logged with full context for audit trails.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        crew_id: Optional[str] = None,
        api_url: str = "https://api.contextgraph.dev",
        log_tool_calls: bool = True,
        log_agent_thoughts: bool = True,
        auto_approve: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the ContextGraph observer.

        Args:
            api_key: ContextGraph API key. Defaults to CG_API_KEY env var.
            crew_id: ID to use as the agent identifier. Defaults to CG_CREW_ID env var.
            api_url: ContextGraph API URL.
            log_tool_calls: Whether to log individual tool calls.
            log_agent_thoughts: Whether to log agent reasoning/thoughts.
            auto_approve: Automatically approve decisions (for testing).
            metadata: Additional metadata to include with all decisions.
        """
        self.api_key = api_key or os.environ.get("CG_API_KEY")
        self.crew_id = crew_id or os.environ.get("CG_CREW_ID")
        self.api_url = api_url.rstrip("/")
        self.log_tool_calls = log_tool_calls
        self.log_agent_thoughts = log_agent_thoughts
        self.auto_approve = auto_approve
        self.metadata = metadata or {}

        if not self.api_key:
            raise ValueError(
                "ContextGraph API key required. Set CG_API_KEY env var or pass api_key."
            )
        if not self.crew_id:
            raise ValueError(
                "ContextGraph crew ID required. Set CG_CREW_ID env var or pass crew_id."
            )

        self._client = httpx.Client(
            base_url=self.api_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

        # Track active decisions by task/agent
        self._active_decisions: Dict[str, str] = {}
        self._crew_decision_id: Optional[str] = None

    def _log_decision(
        self,
        decision_type: str,
        action: str,
        context: Dict[str, Any],
        reference_id: Optional[str] = None,
    ) -> Optional[str]:
        """Log a decision to ContextGraph."""
        try:
            payload = {
                "agent_id": self.crew_id,
                "type": decision_type,
                "action": action,
                "status": "proposed",
                "context": {
                    **context,
                    **self.metadata,
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "crewai",
                },
            }

            if reference_id:
                payload["context"]["reference_id"] = reference_id

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

    def _transition_decision(
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

    # ==================== Crew Callbacks ====================

    def on_crew_start(self, crew: Any) -> None:
        """Called when a crew starts execution."""
        agents = []
        if hasattr(crew, "agents"):
            agents = [
                {"name": a.role, "goal": getattr(a, "goal", None)}
                for a in crew.agents
            ]

        tasks = []
        if hasattr(crew, "tasks"):
            tasks = [
                {"description": t.description[:200] if t.description else None}
                for t in crew.tasks
            ]

        self._crew_decision_id = self._log_decision(
            decision_type="crew_execution",
            action="start_crew",
            context={
                "crew_name": getattr(crew, "name", "unnamed_crew"),
                "agents": agents,
                "tasks": tasks,
                "num_agents": len(agents),
                "num_tasks": len(tasks),
            },
        )

    def on_crew_end(self, crew: Any, output: Any) -> None:
        """Called when a crew finishes execution."""
        if self._crew_decision_id:
            self._transition_decision(
                self._crew_decision_id,
                "executed",
                result={
                    "output": str(output)[:5000] if output else None,
                    "success": True,
                },
            )
            self._crew_decision_id = None

    def on_crew_error(self, crew: Any, error: Exception) -> None:
        """Called when a crew encounters an error."""
        if self._crew_decision_id:
            self._transition_decision(
                self._crew_decision_id,
                "failed",
                result={"error": str(error)},
            )
            self._crew_decision_id = None

    # ==================== Task Callbacks ====================

    def on_task_start(self, task: Any, agent: Any) -> None:
        """Called when a task starts."""
        task_id = str(id(task))
        agent_name = getattr(agent, "role", "unknown_agent")

        decision_id = self._log_decision(
            decision_type="task_execution",
            action="execute_task",
            context={
                "task_description": getattr(task, "description", "")[:500],
                "expected_output": getattr(task, "expected_output", "")[:500],
                "agent_name": agent_name,
                "agent_goal": getattr(agent, "goal", None),
            },
            reference_id=task_id,
        )

        if decision_id:
            self._active_decisions[task_id] = decision_id

    def on_task_end(self, task: Any, output: Any) -> None:
        """Called when a task completes."""
        task_id = str(id(task))
        decision_id = self._active_decisions.pop(task_id, None)

        if decision_id:
            self._transition_decision(
                decision_id,
                "executed",
                result={
                    "output": str(output)[:5000] if output else None,
                },
            )

    def on_task_error(self, task: Any, error: Exception) -> None:
        """Called when a task fails."""
        task_id = str(id(task))
        decision_id = self._active_decisions.pop(task_id, None)

        if decision_id:
            self._transition_decision(
                decision_id,
                "failed",
                result={"error": str(error)},
            )

    # ==================== Agent Callbacks ====================

    def on_agent_action(self, agent: Any, action: str, action_input: Any) -> None:
        """Called when an agent takes an action."""
        agent_name = getattr(agent, "role", "unknown_agent")
        agent_id = f"{agent_name}_{id(agent)}"

        decision_id = self._log_decision(
            decision_type="agent_action",
            action=action,
            context={
                "agent_name": agent_name,
                "action": action,
                "action_input": self._serialize(action_input),
            },
            reference_id=agent_id,
        )

        if decision_id:
            self._active_decisions[f"action_{agent_id}"] = decision_id

    def on_agent_finish(self, agent: Any, output: Any) -> None:
        """Called when an agent finishes an action."""
        agent_name = getattr(agent, "role", "unknown_agent")
        agent_id = f"{agent_name}_{id(agent)}"
        decision_id = self._active_decisions.pop(f"action_{agent_id}", None)

        if decision_id:
            self._transition_decision(
                decision_id,
                "executed",
                result={"output": self._serialize(output)},
            )

    # ==================== Tool Callbacks ====================

    def on_tool_use(
        self, agent: Any, tool_name: str, tool_input: Any, tool_output: Any
    ) -> None:
        """Called when an agent uses a tool."""
        if not self.log_tool_calls:
            return

        agent_name = getattr(agent, "role", "unknown_agent")

        decision_id = self._log_decision(
            decision_type="tool_usage",
            action=tool_name,
            context={
                "agent_name": agent_name,
                "tool_name": tool_name,
                "tool_input": self._serialize(tool_input),
                "tool_output": self._serialize(tool_output)[:2000],
            },
        )

        # Tool calls are instantaneous, so immediately mark as executed
        if decision_id:
            self._transition_decision(decision_id, "executed")

    def on_tool_error(
        self, agent: Any, tool_name: str, tool_input: Any, error: Exception
    ) -> None:
        """Called when a tool fails."""
        if not self.log_tool_calls:
            return

        agent_name = getattr(agent, "role", "unknown_agent")

        decision_id = self._log_decision(
            decision_type="tool_usage",
            action=tool_name,
            context={
                "agent_name": agent_name,
                "tool_name": tool_name,
                "tool_input": self._serialize(tool_input),
            },
        )

        if decision_id:
            self._transition_decision(
                decision_id,
                "failed",
                result={"error": str(error)},
            )

    # ==================== Thought Callbacks ====================

    def on_agent_thought(self, agent: Any, thought: str) -> None:
        """Called when an agent has a thought/reasoning step."""
        if not self.log_agent_thoughts:
            return

        agent_name = getattr(agent, "role", "unknown_agent")

        self._log_decision(
            decision_type="agent_reasoning",
            action="think",
            context={
                "agent_name": agent_name,
                "thought": thought[:2000],
            },
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


# Convenience function for CrewAI integration
def create_observer(**kwargs) -> ContextGraphObserver:
    """Create a ContextGraph observer for CrewAI."""
    return ContextGraphObserver(**kwargs)
