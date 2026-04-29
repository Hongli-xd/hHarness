# HistRAG - Historical Research Agent

Based on **OpenHarness** (Agent Framework) + **LightRAG** (Knowledge Graph) for historical research.

## Core Architecture

```
histrag CLI (Typer)
    │
    ▼
openharness.ui.runtime.build_runtime()
    │
    ├── API Client (Anthropic/OpenAI)
    ├── ToolRegistry (create_default_tool_registry + historical tools)
    ├── SkillRegistry (histrag skills directory)
    ├── PermissionChecker (read-only mode)
    └── QueryEngine (system_prompt=historian prompt)
         │
         ▼
    Agent Loop (run_query)
         │
         ▼
    Tool Execution → kg_query / rag_query / cite
         │
         ▼
    LightRAG Client → Knowledge Graph
```

## Key Integration Points

### 1. `integration.py` - OpenHarness Integration

```python
from histrag.integration import create_historical_runtime, run_historical_query

# Create full Runtime
runtime = create_historical_runtime(cwd=".", model="claude-sonnet-4-20250514")
await runtime.rag_client.initialize()

# Use Agent
async for event in runtime.engine.submit_message("...."):
    print(event)

await runtime.rag_client.finalize()
```

### 2. Tools - Historical Tools Registration

```python
from histrag.tools import create_historical_tool_registry

# Historical tools have highest priority, overriding same-name tools
hist_registry = create_historical_tool_registry(rag_client)
for name, tool in hist_registry._tools.items():
    base_registry._tools[name] = tool
```

### 3. Skills - Skills Loading

```python
from histrag.skills.loader import load_historical_skill_registry

# Load chronology, comparison, counterfactual, annales methods
registry = load_historical_skill_registry(cwd=".")
```

## Usage

### Stable Web Startup

From the repository root, run:

```bash
./scripts/start_histrag_web.sh
```

The script checks the virtual environment, installs missing Python dependencies,
verifies local map resources, starts Neo4j when available through Homebrew, and
restarts the HistRAG web service at:

```text
http://127.0.0.1:7860
```

Neo4j Browser is available at:

```text
http://127.0.0.1:7474
username: neo4j
password: 00000000
```

To stop the web service:

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/histrag.web.plist
```

### Installation

```bash
cd /home/selom/projects/literag/Harness
pip install -e .
```

### CLI Commands

```bash
# Create Knowledge Graph (Indexing)
python -m histrag create-graph <path/to/document.txt>

# Example with Chinese historical text
python -m histrag create-graph /home/selom/project/hHarness/LightRAG/input/元和郡县图志.txt

# Agent Mode (full tool calling)
python -m histrag query "《元和郡县图志》是以唐宪宗'元和'年间的疆域为准的。请列举书中记录的全国'道'的名称。相比于唐初的'贞观十道'或开元'十五道'，元和年间的'道'在划分和数量上发生了哪些关键变化？这种变化反映了中晚唐怎样的政治格局？"

# Direct RAG Mode (fast query)
python -m histrag lightrag "《元和郡县图志》是以唐宪宗'元和'年间的疆域为准的。请列举书中记录的全国'道'的名称。相比于唐初的'贞观十道'或开元'十五道'，元和年间的'道'在划分和数量上发生了哪些关键变化？这种变化反映了中晚唐怎样的政治格局？"

# Interactive Mode
python -m histrag interactive

# List Available Tools
python -m histrag tools

# Version
python -m histrag version-cmd
```

### Configuration

Edit `rag_config.yaml` to customize:

```yaml
# LLM Configuration
llm:
  model_func: "anthropic"
  model_name: "MiniMax-M2.7"
  api_key: "your-api-key"
  base_url: "https://api.minimaxi.com/anthropic"
  max_tokens: 64000
  max_async: 3

# Embedding Configuration
embedding:
  model: "Qwen/Qwen3-Embedding-4B"
  dimension: 1024
  batch_size: 5  # Adjust based on API limits

# Storage Configuration
storage:
  kv_storage: JsonKVStorage
  vector_storage: NanoVectorDBStorage
  graph_storage: Neo4JStorage
  doc_status_storage: JsonDocStatusStorage

# Neo4j Configuration
neo4j:
  uri: "bolt://localhost:7687"
  username: "neo4j"
  password: "your-password"
```

### Python API

```python
import asyncio
from histrag.integration import create_historical_runtime
from openharness.engine.stream_events import AssistantTextDelta, ToolExecutionCompleted

async def main():
    runtime = create_historical_runtime(
        cwd=".",
        model="claude-sonnet-4-20250514",
        max_turns=8,
    )

    await runtime.rag_client.initialize()

    try:
        async for event in runtime.engine.submit_message("史记的作者是谁？"):
            if isinstance(event, AssistantTextDelta):
                print(event.text, end="")
            elif isinstance(event, ToolExecutionCompleted):
                print(f"\n[TOOL: {event.tool_name}]")

    finally:
        await runtime.rag_client.finalize()

asyncio.run(main())
```

## Directory Structure

```
Harness/
├── histrag/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py              # CLI entry (Typer)
│   ├── integration.py      # OpenHarness integration (key)
│   │
│   ├── tools/
│   │   ├── kg_query_tool.py   # Knowledge graph query tool
│   │   ├── rag_query_tool.py  # RAG query tool
│   │   ├── cite_tool.py       # Citation tool
│   │   └── registry.py        # Tool registration
│   │
│   ├── skills/
│   │   ├── loader.py          # Skills loader
│   │   ├── chronology.md        # Chronology method
│   │   ├── comparison.md       # Comparison method
│   │   ├── counterfactual.md   # Counterfactual analysis
│   │   └── annales.md          # Annales school
│   │
│   ├── prompts/
│   │   └── historian.py        # Historian system prompt
│   │
│   ├── ohmo/
│   │   ├── soul.md            # Historian personality
│   │   ├── identity.md        # Historian identity
│   │   └── memory/
│   │       └── credibility_guide.md  # Source credibility guide
│   │
│   ├── lightrag/
│   │   ├── client.py          # LightRAG async client
│   │   ├── config.py          # Config loader
│   │   └── credibility.py     # Credibility annotation layer
│   │
│   └── coordinator/
│       └── historian.py        # 2-agent coordinator
│
└── pyproject.toml
```

## Historical Tools

| Tool | Description |
|------|-------------|
| `kg_query` | Knowledge graph query: entity query, fuzzy search, relation paths |
| `rag_query` | RAG query: generate answer with LLM |
| `rag_data_query` | RAG data query: return structured results (no LLM) |
| `cite` | Citation: insert citations, trace sources, list citations |

## Source Credibility Annotation

Historical sources are categorized into three types:

- **[一手文献]** (Primary Source) - Contemporary documents, e.g., "Records of the Grand Historian", "Book of Han"
- **[二手研究]** (Secondary Source) - Later research, e.g., academic monographs
- **[争议性说法]** (Disputed) - Disputed interpretations

## Inherited from OpenHarness

- ✅ QueryEngine core loop (streaming tool calls)
- ✅ Skills system (on-demand .md skill files)
- ✅ Memory system (session context storage)
- ✅ Permissions system (read-only mode)
- ✅ API Layer (multi-model support)

## Removed Modules

- ❌ Channels (Slack/Discord/Telegram)
- ❌ Autopilot
- ❌ Sandbox
- ❌ Vim/Keybindings/TUI
- ❌ Complex Swarm (using simplified Coordinator)
