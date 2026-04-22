# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HistRAG (Historical Research Agent) is a research agent for historical text analysis, built on:
- **OpenHarness** (agent framework) - provides the core agent loop, skills system, and API client abstraction
- **LightRAG** (knowledge graph) - provides indexing and querying over historical documents
- **Custom Layer** (`histrag/`) - historian personality, specialized tools, and methodology skills

## Commands

```bash
# Install in development mode
cd /home/selom/project/hHarness/Harness
pip install -e .

# Run tests
pytest

# Run a single test file
pytest tests/test_integration.py

# Lint
ruff check histrag/

# CLI commands
python -m histrag create-graph <path>   # Index documents into knowledge graph
python -m histrag query "<question>"    # Full agent mode with tool calling
python -m histrag lightrag "<question>"  # Direct RAG query (no agent)
python -m histrag interactive            # Interactive mode
python -m histrag tools                  # List available tools
python -m histrag version-cmd            # Show version
```

## Architecture

```
histrag/
├── integration.py       # Entry point: create_historical_runtime() builds the full stack
├── agent/engine.py     # AgentEngine - simplified agent loop (replaces OpenHarness QueryEngine)
├── coordinator/        # 2-agent coordination (HistorianCoordinator + KGVerifierAgent)
├── tools/              # Historical research tools (CiteTool, RAGQueryTool, etc.)
├── lightrag/client.py  # Async wrapper around LightRAG operations
├── skills/loader.py     # Loads historian methodology skills (chronology, comparison, etc.)
└── prompts/historian.py # Builds system prompt from ohmo/ files + skills
```

**Runtime Creation Flow** (`integration.py`):
1. `create_historical_runtime()` → initializes LightRAG client
2. Builds system prompt from `ohmo/soul.md`, `ohmo/identity.md`, skills, and memory
3. Creates tool registry with historical tools (override OpenHarness defaults)
4. Returns `HistorianRuntime(engine, rag_client, tool_registry)`

**Agent Loop** (`agent/engine.py`):
- `submit_message()` is an async generator yielding stream events
- Handles tool call execution, error recovery, and message building
- Uses `api_client.stream_message()` for LLM calls
- **Auto-invocation**: After generating final answer (no tool calls), automatically invokes `linked_view` to extract events and places from the answer
- Events: `AssistantTextDelta`, `AssistantTurnComplete`, `ToolExecutionStarted`, `ToolExecutionCompleted`, `ErrorEvent`

**2-Agent Coordination** (`coordinator/historian.py`):
- `HistorianCoordinator` manages main agent + KG verifier sub-agent
- Claims are verified against knowledge graph before inclusion in narrative

## Key Integration Points

```python
from histrag.agent.events import (
    AssistantTextDelta,
    AssistantTurnComplete,
    ToolExecutionStarted,
    ToolExecutionCompleted,
    ErrorEvent,
)

# Create runtime with full tool calling
runtime = create_historical_runtime(cwd=".", model="claude-sonnet-4-20250514")
await runtime.rag_client.initialize()
async for event in runtime.engine.submit_message("..."):
    print(event)
await runtime.rag_client.finalize()
```

## Tool Priority

Historical tools in `tools/registry.py` override same-name tools from OpenHarness when merged:
- `kg_query` - entity/relation queries against knowledge graph
- `rag_query` - LLM-powered RAG queries
- `rag_data_query` - structured retrieval (no LLM)
- `cite` - citation management and source tracing
- `linked_view` - timeline + map visualization (auto-invoked after answer generation)

**Linked View Auto-invocation**: After the model generates its final answer, the engine automatically invokes `linked_view` to extract events and places from the response and produce a linked timeline+map HTML visualization. This requires no explicit tool call from the model.

## Configuration

Edit `Harness/rag_config.yaml`:
- `llm` section: model, api_key, base_url
- `embedding` section: model, dimension, batch_size
- `storage` section: JsonKVStorage, NanoVectorDBStorage, Neo4JStorage
- `neo4j` section: connection settings

## OpenHarness Inheritance

HistRAG uses these OpenHarness components directly:
- `openharness.api.AnthropicApiClient` / `ApiMessageRequest`
- `openharness.skills.load_skill_registry`
- `openharness.agent.tools.ToolRegistry`, `ToolExecutionContext`, `ToolResult`

## Source Credibility

Three-tier annotation system (`lightrag/credibility.py`):
- `[一手文献]` - Primary sources (contemporary documents)
- `[二手研究]` - Secondary sources (later research)
- `[争议性说法]` - Disputed interpretations
