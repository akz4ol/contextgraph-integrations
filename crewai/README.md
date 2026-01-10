# ContextGraph CrewAI Integration

Automatically log all CrewAI crew and agent decisions to ContextGraph Cloud for audit trails, policy enforcement, and compliance reporting.

## Installation

```bash
pip install contextgraph-crewai
```

## Quick Start

```python
import os
from crewai import Agent, Task, Crew
from contextgraph_observer import ContextGraphObserver

# Initialize the observer
observer = ContextGraphObserver(
    api_key=os.environ["CG_API_KEY"],
    crew_id="my-research-crew"
)

# Create your agents
researcher = Agent(
    role="Researcher",
    goal="Research and analyze topics",
    backstory="Expert researcher with analytical skills"
)

writer = Agent(
    role="Writer",
    goal="Write clear, engaging content",
    backstory="Professional writer with journalism background"
)

# Create tasks
research_task = Task(
    description="Research the latest AI governance trends",
    agent=researcher,
    expected_output="Summary of key trends"
)

write_task = Task(
    description="Write a blog post about AI governance",
    agent=writer,
    expected_output="Blog post draft"
)

# Create crew with the observer
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, write_task],
    callbacks=[observer]  # Add the observer here
)

# Every action is now logged to ContextGraph
result = crew.kickoff()
```

## What Gets Logged

| Event | Decision Type | What's Captured |
|-------|---------------|-----------------|
| Crew start | `crew_execution` | Agents, tasks, configuration |
| Task start | `task_execution` | Task description, assigned agent |
| Agent action | `agent_action` | Action type, inputs |
| Tool usage | `tool_usage` | Tool name, input, output |
| Agent thought | `agent_reasoning` | Reasoning/thinking steps |
| Task completion | - | Task output, success/failure |
| Crew completion | - | Final output, execution summary |

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `api_key` | `$CG_API_KEY` | ContextGraph API key |
| `crew_id` | `$CG_CREW_ID` | Identifier for this crew |
| `api_url` | `https://contextgraph-api.fly.dev` | API endpoint |
| `log_tool_calls` | `True` | Log individual tool usages |
| `log_agent_thoughts` | `True` | Log agent reasoning steps |
| `auto_approve` | `False` | Auto-approve decisions (testing) |
| `metadata` | `{}` | Additional metadata for all decisions |

## Adding Custom Metadata

```python
observer = ContextGraphObserver(
    api_key=os.environ["CG_API_KEY"],
    crew_id="content-team",
    metadata={
        "environment": "production",
        "project": "blog-automation",
        "team": "marketing"
    }
)
```

## Viewing Decisions

Query decisions via API:

```bash
curl https://contextgraph-api.fly.dev/v1/decisions \
  -H "Authorization: Bearer $CG_API_KEY"
```

## Policy Enforcement

Create policies in ContextGraph to control crew behavior:

```json
{
  "name": "require-approval-for-external-tools",
  "condition": {
    "and": [
      { "field": "type", "equals": "tool_usage" },
      { "field": "context.tool_name", "in": ["web_search", "api_call"] }
    ]
  },
  "effect": "require_approval"
}
```

Now any external tool usage will require human approval before proceeding.

## Example: Audit Trail

After a crew run, you can retrieve the full audit trail:

```python
import httpx

client = httpx.Client(
    base_url="https://contextgraph-api.fly.dev",
    headers={"Authorization": f"Bearer {os.environ['CG_API_KEY']}"}
)

# Get all decisions for this crew
response = client.get("/v1/decisions", params={"agent_id": "my-research-crew"})
decisions = response.json()

for decision in decisions["data"]:
    print(f"{decision['type']}: {decision['action']} - {decision['status']}")
```

## License

Apache 2.0 - see [LICENSE](../LICENSE).
