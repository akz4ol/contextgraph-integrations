# ContextGraph LangChain Integration

Automatically log all LangChain agent decisions to ContextGraph Cloud for audit trails, policy enforcement, and compliance reporting.

## Installation

```bash
pip install contextgraph-langchain
```

## Quick Start (LangChain v1+)

LangChain v1 introduced a new middleware system. Use `contextgraph_middleware` with `create_agent()`:

```python
import os
from langchain.agents import create_agent
from contextgraph_middleware import contextgraph_middleware

# Create agent with ContextGraph middleware
agent = create_agent(
    model="openai:gpt-4o",
    tools=[search_tool, calculator_tool],
    middleware=contextgraph_middleware(
        api_key=os.environ["CG_API_KEY"],
        agent_id="my-research-agent"
    )
)

# Every model call and tool execution is now logged
result = agent.invoke({"input": "What's the weather in NYC?"})
```

## What Gets Logged

| Event | Decision Type | What's Captured |
|-------|---------------|-----------------|
| Model call | `model_call` | Message count, last message |
| Tool execution | `tool_execution` | Tool name, input, output/error |

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `api_key` | `$CG_API_KEY` | ContextGraph API key |
| `agent_id` | `$CG_AGENT_ID` | Registered agent ID |
| `api_url` | `https://contextgraph-api.fly.dev` | API endpoint |
| `log_model_calls` | `True` | Log model invocations |
| `log_tool_calls` | `True` | Log tool executions |
| `auto_approve` | `False` | Auto-approve decisions (testing) |
| `metadata` | `{}` | Additional metadata for all decisions |

## Adding Custom Metadata

```python
from contextgraph_middleware import contextgraph_middleware

middleware = contextgraph_middleware(
    api_key=os.environ["CG_API_KEY"],
    agent_id="trading-bot",
    metadata={
        "environment": "production",
        "version": "1.2.0",
        "team": "trading-systems"
    }
)
```

## Legacy Support (LangChain < 1.0)

For older LangChain versions using `AgentExecutor`, use the callback handler:

```python
from langchain.agents import AgentExecutor
from contextgraph_callback import ContextGraphCallback

callback = ContextGraphCallback(
    api_key=os.environ["CG_API_KEY"],
    agent_id="my-agent"
)

executor = AgentExecutor(
    agent=agent,
    tools=tools,
    callbacks=[callback]
)
```

> **Note:** `AgentExecutor` is deprecated in LangChain v1. Migrate to `create_agent()` with middleware for new projects.

## Viewing Decisions

Query decisions via API:

```bash
curl https://contextgraph-api.fly.dev/v1/decisions \
  -H "Authorization: Bearer $CG_API_KEY"
```

## Policy Enforcement

Create policies in ContextGraph to control agent behavior:

```json
{
  "name": "block-dangerous-tools",
  "condition": {
    "and": [
      { "field": "action", "in": ["shell_execute", "file_delete"] }
    ]
  },
  "effect": "deny"
}
```

Now any attempt to use blocked tools will be logged and rejected.

## License

Apache 2.0 - see [LICENSE](../LICENSE).
