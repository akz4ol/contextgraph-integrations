# ContextGraph Integrations

Official Python integrations for [ContextGraph Cloud](https://contextgraph.dev) - audit trails, policy enforcement, and compliance reporting for AI agents.

## Available Integrations

| Package | Framework | Install |
|---------|-----------|---------|
| [contextgraph-langchain](./langchain) | LangChain | `pip install contextgraph-langchain` |
| [contextgraph-crewai](./crewai) | CrewAI | `pip install contextgraph-crewai` |

## Quick Start

### LangChain

```python
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from contextgraph_langchain import ContextGraphCallback

callback = ContextGraphCallback(
    api_key="your-api-key",
    agent_id="my-agent"
)

llm = ChatOpenAI(model="gpt-4o")
agent = create_react_agent(llm, tools)

# Run with callback
result = agent.invoke(
    {"messages": [("user", "What's the weather?")]},
    config={"callbacks": [callback]}
)
```

### CrewAI

```python
from crewai import Crew
from contextgraph_observer import ContextGraphObserver

observer = ContextGraphObserver(
    api_key="your-api-key",
    crew_id="my-crew"
)

crew = Crew(
    agents=[agent1, agent2],
    tasks=[task1, task2],
    callbacks=[observer]
)
```

## What Gets Logged

Every integration automatically captures:

- **Tool invocations** - What tools are being called and why
- **Tool executions** - Inputs, outputs, and errors
- **Agent reasoning** - Thought processes and decisions
- **Task lifecycle** - Start, completion, and failures

All events are logged to ContextGraph Cloud with full context for:
- Audit trails
- Policy enforcement
- Compliance reporting
- Debugging and observability

## Getting an API Key

1. Sign up at [cloud.contextgraph.dev](https://cloud.contextgraph.dev)
2. Create an organization
3. Register your agent
4. Copy the API key

## Documentation

- [ContextGraph Cloud Docs](https://docs.contextgraph.dev)
- [LangChain Integration](./langchain/README.md)
- [CrewAI Integration](./crewai/README.md)

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md).

## License

Apache 2.0 - see [LICENSE](LICENSE)

## Support

- GitHub Issues: [contextgraph-integrations/issues](https://github.com/akz4ol/contextgraph-integrations/issues)
- Email: blog.mot2gmob@gmail.com
- Discord: [Join our community](https://discord.gg/contextgraph)
