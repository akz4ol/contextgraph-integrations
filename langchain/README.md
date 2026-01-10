# ContextGraph LangChain Integration

Automatically log all LangChain agent decisions to ContextGraph Cloud for audit trails, policy enforcement, and compliance reporting.

## Installation

```bash
pip install contextgraph-langchain
```

## Quick Start

```python
import os
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI
from contextgraph_callback import ContextGraphCallback

# Initialize the callback
callback = ContextGraphCallback(
    api_key=os.environ["CG_API_KEY"],
    agent_id="my-langchain-agent"
)

# Create your agent with the callback
llm = ChatOpenAI(model="gpt-4")
agent = create_openai_tools_agent(llm, tools, prompt)

executor = AgentExecutor(
    agent=agent,
    tools=tools,
    callbacks=[callback]  # Add the callback here
)

# Every tool call is now logged to ContextGraph
result = executor.invoke({"input": "What's the weather in NYC?"})
```

## What Gets Logged

By default, the callback logs:

| Event | Decision Type | What's Captured |
|-------|---------------|-----------------|
| Tool invocation | `tool_invocation` | Tool name, input, agent reasoning |
| Tool execution | `tool_execution` | Tool name, input, output/error |
| Chain execution | `chain_execution` | Chain name, inputs, outputs |

Optionally, you can also log LLM calls:

```python
callback = ContextGraphCallback(
    api_key=os.environ["CG_API_KEY"],
    agent_id="my-agent",
    log_llm_calls=True  # Enable LLM call logging
)
```

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `api_key` | `$CG_API_KEY` | ContextGraph API key |
| `agent_id` | `$CG_AGENT_ID` | Registered agent ID |
| `api_url` | `https://api.contextgraph.dev` | API endpoint |
| `log_llm_calls` | `False` | Log individual LLM calls |
| `log_chain_calls` | `True` | Log chain executions |
| `auto_approve` | `False` | Auto-approve decisions (testing) |
| `metadata` | `{}` | Additional metadata for all decisions |

## Adding Custom Metadata

```python
callback = ContextGraphCallback(
    api_key=os.environ["CG_API_KEY"],
    agent_id="trading-bot",
    metadata={
        "environment": "production",
        "version": "1.2.0",
        "team": "trading-systems"
    }
)
```

## Viewing Decisions

After running your agent, view decisions in the ContextGraph dashboard:

```
https://cloud.contextgraph.dev/decisions
```

Or query via API:

```bash
curl https://api.contextgraph.dev/v1/decisions \
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

MIT License - see LICENSE file.
