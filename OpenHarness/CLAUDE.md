# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OpenHarness delivers lightweight agent infrastructure: tool-use, skills, memory, and multi-agent coordination. `ohmo` is a personal AI agent built on OpenHarness that works over long sessions in chat platforms (Feishu, Slack, Telegram, Discord).

## Architecture

### Core Subsystems (in `src/openharness/`)

| Subsystem | Purpose |
|-----------|---------|
| `engine/` | Agent loop — query → stream → tool-call cycle |
| `tools/` | 43+ tools (file I/O, shell, search, web, MCP) |
| `skills/` | On-demand skill loading from `.md` files |
| `permissions/` | Multi-level permission modes, path rules |
| `hooks/` | PreToolUse/PostToolUse lifecycle events |
| `commands/` | 54 commands (/help, /commit, /plan, /resume, etc.) |
| `mcp/` | Model Context Protocol client |
| `memory/` | Persistent cross-session knowledge |
| `tasks/` | Background task management |
| `coordinator/` | Subagent spawning, team coordination |
| `prompts/` | System prompt assembly, CLAUDE.md discovery |
| `config/` | Multi-layer settings, migrations |
| `channels/` | Chat platform adapters (Slack, Discord, Telegram, Feishu, etc.) |

### The Agent Loop

```python
while True:
    response = await api.stream(messages, tools)
    if response.stop_reason != "tool_use":
        break
    for tool_call in response.tool_uses:
        result = await harness.execute_tool(tool_call)
    messages.append(tool_results)
```

### Key Entry Points

- `oh` CLI entry: `src/openharness/cli.py`
- `ohmo` CLI entry: `ohmo/cli.py`
- Gateway service: `ohmo/gateway/service.py`
- Query engine: `src/openharness/engine/query_engine.py`

## Development Commands

### Setup
```bash
uv sync --extra dev    # Install with dev dependencies
```

### Testing
```bash
uv run pytest -q                    # 114 unit/integration tests
python scripts/test_harness_features.py   # Harness E2E
python scripts/test_real_skills_plugins.py  # Real plugins E2E
python scripts/test_cli_flags.py      # CLI flags E2E
```

### Running
```bash
oh                           # Start CLI agent
ohmo                         # Start personal agent
ohmo gateway start           # Start gateway for chat platforms
```

## Key Patterns

### Tool Definition
```python
from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult
from pydantic import BaseModel, Field

class MyToolInput(BaseModel):
    query: str = Field(description="Search query")

class MyTool(BaseTool):
    name = "my_tool"
    description = "Does something useful"
    input_model = MyToolInput

    async def execute(self, arguments: MyToolInput, context: ToolExecutionContext) -> ToolResult:
        return ToolResult(output=f"Result for: {arguments.query}")
```

### Provider Configuration
```bash
oh setup                      # Interactive provider wizard
oh provider list              # Show available providers
oh provider use <profile>     # Switch active provider
```

### Adding Custom Skills
Create `~/.openharness/skills/my-skill.md`:
```markdown
---
name: my-skill
description: Expert guidance for my specific domain
---

# My Skill

## When to use
Use when the user asks about [your domain].

## Workflow
1. Step one
2. Step two
```

### Plugin Compatibility
OpenHarness is compatible with [claude-code plugins](https://github.com/anthropics/claude-code/tree/main/plugins). Place plugins in `.openharness/plugins/`.

## ohmo Personal Agent

`ohmo` workspace structure (`~/.ohmo/`):
- `soul.md` — long-term agent personality
- `identity.md` — agent identity
- `user.md` — user profile and preferences
- `memory/` — persistent memory
- `gateway.json` — provider and channel configuration

## Provider Support

| Provider | Auth Method |
|----------|-------------|
| Claude official | API key |
| Claude Subscription | `~/.claude/.credentials.json` bridge |
| OpenAI | API key |
| Codex Subscription | `~/.codex/auth.json` bridge |
| GitHub Copilot | OAuth device flow |
| Moonshot/Kimi | Anthropic-compatible API |
| Ollama (local) | OpenAI-compatible endpoint |

## CLI Reference

```
oh [OPTIONS] COMMAND [ARGS]

Session:     -c/--continue, -r/--resume, -n/--name
Model:       -m/--model, --effort, --max-turns
Output:      -p/--print, --output-format text|json|stream-json
Permissions: --permission-mode, --dangerously-skip-permissions
Context:     -s/--system-prompt, --append-system-prompt, --settings
Advanced:    -d/--debug, --mcp-config, --bare

Subcommands: oh setup | oh provider | oh auth | oh mcp | oh plugin
```
