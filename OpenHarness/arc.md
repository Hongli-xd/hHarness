# OpenHarness Architecture Analysis

## 1. Project Structure

```
/home/selom/projects/literag/OpenHarness/
├── src/openharness/          # Core Python library (openharness-ai package)
│   ├── api/                  # LLM API clients (Anthropic, OpenAI, Codex, Copilot)
│   ├── auth/                 # Authentication handlers
│   ├── autopilot/            # Repo autopilot functionality
│   ├── bridge/               # Claude Code subscription bridge
│   ├── channels/             # Chat platform integrations (event bus + implementations)
│   ├── channels/bus/          # Message bus for channel communication
│   ├── channels/impl/         # Platform-specific adapters (Slack, Discord, Telegram, Feishu, etc.)
│   ├── commands/             # CLI commands (/help, /commit, /plan, etc.)
│   ├── config/               # Settings management, paths, schema
│   ├── coordinator/          # Multi-agent coordination, team management
│   ├── engine/               # Core agent loop (query engine, messages, cost tracking)
│   ├── hooks/                # PreToolUse/PostToolUse lifecycle hooks
│   ├── keybindings/          # Keyboard shortcut handling
│   ├── mcp/                  # Model Context Protocol client
│   ├── memory/               # Persistent cross-session memory
│   ├── output_styles/        # Output formatting
│   ├── permissions/          # Multi-level permission checking
│   ├── personalization/      # User preferences and customization
│   ├── plugins/              # Plugin loader and installer (compatible with claude-code plugins)
│   ├── prompts/              # System prompt assembly, CLAUDE.md discovery
│   ├── sandbox/              # Sandboxed execution environment
│   ├── services/             # Background services (cron, session storage, LSP, OAuth)
│   ├── skills/               # On-demand skill loading from .md files
│   ├── state/                # Application state management
│   ├── swarm/                # Multi-agent spawning, team coordination
│   ├── tasks/                # Background task management
│   ├── themes/               # UI themes
│   ├── tools/                # 43+ tool implementations (file I/O, shell, search, web, MCP)
│   ├── ui/                   # React TUI backend protocol + Textual app
│   ├── utils/                # Utility functions
│   ├── vim/                  # Vim integration
│   ├── voice/                # Voice input handling
│   └── cli.py                # Main CLI entry point (59KB - large file with all commands)
│
├── ohmo/                     # Personal AI agent app built on OpenHarness
│   ├── cli.py                # ohmo CLI entry point
│   ├── gateway/              # Gateway service for chat platforms
│   │   ├── service.py        # Gateway lifecycle management
│   │   ├── bridge.py         # Gateway bridge to OpenHarness
│   │   ├── config.py         # Gateway configuration
│   │   ├── runtime.py        # Session runtime pool
│   │   └── models.py         # Gateway state models
│   ├── workspace.py          # Workspace management (~/.ohmo/)
│   ├── memory.py             # ohmo-specific memory
│   ├── prompts.py            # ohmo bootstrap prompts
│   └── session_storage.py    # Session persistence
│
├── frontend/
│   └── terminal/             # React/Ink TUI (terminal UI)
│       ├── package.json      # npm package with ink, react dependencies
│       └── src/
│           ├── index.tsx     # TUI entry point
│           ├── App.tsx       # Main React app component
│           └── components/   # UI components (Composer, ConversationView, ModalHost, etc.)
│
├── autopilot-dashboard/      # React dashboard for autopilot (separate Vite app)
│   └── package.json
│
├── tests/                    # Comprehensive test suite (30+ test directories)
│   ├── test_engine/          # Engine/query engine tests
│   ├── test_tools/           # Tool tests
│   ├── test_skills/         # Skills system tests
│   ├── test_hooks/          # Hook system tests
│   ├── test_channels/       # Channel adapter tests
│   ├── test_coordinator/    # Multi-agent coordination tests
│   ├── test_swarm/          # Swarm/team tests
│   ├── test_mcp/            # MCP protocol tests
│   ├── test_ohmo/           # ohmo-specific tests
│   └── ...                   # Many more test modules
│
├── docs/                     # Documentation
│   ├── SHOWCASE.md           # Usage examples and patterns
│   └── autopilot/           # Autopilot documentation
│
├── scripts/                  # Installation and test scripts
├── assets/                   # Logos and images
├── pyproject.toml            # Python package configuration
├── CLAUDE.md                # Claude Code guidance
├── README.md                # Project README
└── CHANGELOG.md             # Version history
```

---

## 2. Technology Stack

### Languages
- **Python 3.10+** - Core library, CLI, agent engine
- **TypeScript/React** - Terminal UI (ink framework)
- **JavaScript** - Autopilot dashboard

### Key Python Libraries

| Category | Libraries |
|----------|----------|
| **LLM APIs** | `anthropic`, `openai` |
| **CLI** | `typer`, `prompt-toolkit`, `questionary` |
| **TUI** | `textual`, `rich` |
| **Validation** | `pydantic` |
| **HTTP** | `httpx`, `websockets` |
| **Protocol** | `mcp` (Model Context Protocol) |
| **Chat Platforms** | `slack-sdk`, `python-telegram-bot`, `discord.py`, `lark-oapi` |
| **Scheduling** | `croniter`, `watchfiles` |
| **Clipboard** | `pyperclip` |
| **Testing** | `pytest`, `pytest-asyncio`, `pexpect` |

### Key Frontend Libraries (Terminal TUI)
- **ink** - React for CLI (5.1.0)
- **react** (18.3.1)
- **marked** - Markdown rendering

---

## 3. Core Components and Their Relationships

### Agent Loop (Engine)
The heart of the system in `/home/selom/projects/literag/OpenHarness/src/openharness/engine/`:

```
QueryEngine (query_engine.py)
    ├── Manages conversation history (messages)
    ├── Coordinates with API client for streaming
    ├── Routes tool executions through permissions/hooks
    └── Handles auto-compaction when context is too long

run_query() (query.py) - The core loop:
    while True:
        response = await api.stream(messages, tools)
        if response.stop_reason != "tool_use":
            break  # Model is done
        for tool_call in response.tool_uses:
            result = await harness.execute_tool(tool_call)
        messages.append(tool_results)
```

### Tool System (`tools/`)
- **43+ tools** organized in individual files
- Base class: `BaseTool` in `base.py`
- Tool registry in `registry.py` (92KB - largest file)
- Tools include: file I/O (Read, Write, Edit, Glob, Grep), Bash, Web search/fetch, MCP, Notebook, Agent spawning, Task management, Cron, Skills, etc.

### Permissions System (`permissions/`)
- Multi-level permission modes: Default (ask), Auto (allow all), Plan (read-only)
- Path-level rules with glob patterns
- Built-in sensitive path protection for credentials
- PreToolUse/PostToolUse hook integration

### Hooks System (`hooks/`)
- Lifecycle event hooks: `PreToolUse`, `PostToolUse`
- Hook executor in `executor.py`
- Hot-reload support for development
- Compatible with claude-code plugin hooks format

### Skills System (`skills/`)
- On-demand loading from `.md` files
- Registry of available skills
- Loader discovers skills from filesystem
- Compatible with anthropics/skills format

### Multi-Agent Coordination (`coordinator/`, `swarm/`)
- **Coordinator**: Team coordination, mode management
- **Swarm**: Subagent spawning, mailbox messaging, lockfiles
- Team registry and lifecycle management
- In-process and subprocess agent backends

### Channels System (`channels/`)
- Event bus architecture for loose coupling
- Platform adapters: Slack, Discord, Telegram, Feishu, DingTalk, Email, Matrix, QQ, WhatsApp, MoChat
- Manager for routing messages between platforms

### Memory System (`memory/`)
- Persistent cross-session knowledge
- Memory file scanning and searching
- Project-level and workspace-level memory

### API Layer (`api/`)
- Abstract client interface (`SupportsStreamingMessages` protocol)
- Implementations: `AnthropicClient`, `OpenAIClient`, `CopilotClient`, `CodexClient`
- Provider registry for multi-backend support
- Retry with exponential backoff

---

## 4. Entry Points

### Main CLI Entry: `oh`
```bash
openharness = "openharness.cli:app"  # pyproject.toml
oh = "openharness.cli:app"
ohh = "openharness.cli:app"
```

- **File**: `/home/selom/projects/literag/OpenHarness/src/openharness/cli.py` (59KB)
- **Framework**: Typer CLI framework
- **Subcommands**: `mcp`, `plugin`, `auth`, `provider`, `cron`, `autopilot`

### Alternative Entry: `python -m openharness`
```python
# src/openharness/__main__.py
from openharness.cli import app
if __name__ == "__main__":
    app()
```

### ohmo CLI Entry
```bash
ohmo = "ohmo.cli:app"  # pyproject.toml
```
- **File**: `/home/selom/projects/literag/OpenHarness/ohmo/cli.py`
- **Commands**: `init`, `config`, `gateway` (start/stop/restart/status)

### ohmo Gateway Service
- **File**: `/home/selom/projects/literag/OpenHarness/ohmo/gateway/service.py`
- Bridges chat platforms to the agent runtime
- Manages session pools and channel adapters

### Terminal UI Entry
```bash
# frontend/terminal/package.json
"start": "tsx src/index.tsx"
```
- **File**: `/home/selom/projects/literag/OpenHarness/frontend/terminal/src/index.tsx`
- React/Ink TUI with components for conversation, permissions, etc.

---

## 5. Architectural Patterns

### Layered Architecture
```
CLI/UI Layer
    ↓
Commands / Commands Runtime
    ↓
QueryEngine (Agent Loop)
    ↓
API Clients (Anthropic, OpenAI, etc.)
```

### Event-Driven Channels
- Message bus pattern in `channels/bus/`
- Platform adapters publish/subscribe to events
- Decoupled architecture allows multiple chat platforms

### Plugin Architecture
- Compatible with claude-code plugins
- Plugins can add: commands, hooks, agents, MCP servers
- Hot-reloadable hooks

### Agent Harness Pattern
```
Harness = Tools + Knowledge + Observation + Action + Permissions
```
The harness wraps around an LLM to make it a functional agent:
- **Tools**: File I/O, shell, search, web, MCP
- **Knowledge**: Skills loaded on-demand
- **Observation**: Memory, context management
- **Action**: Tool execution with permissions
- **Permissions**: Safety boundaries

### Coordinator/Worker Pattern (Multi-Agent)
- `coordinator/` manages team-level coordination
- `swarm/` handles subagent spawning
- Subprocess teammates run in headless worker mode
- Real-time polling for agent status

---

## 6. Data Flow

### Interactive Session Flow
```
User Input (oh)
    ↓
CLI (cli.py) → RuntimeBundle
    ↓
QueryEngine.submit_message()
    ↓
API Client.stream_message() → LLM API
    ↓
[For each tool_use in response]
    ↓
PermissionChecker.evaluate()
    ↓
HookExecutor.execute(PreToolUse)
    ↓
Tool.execute()
    ↓
HookExecutor.execute(PostToolUse)
    ↓
Results appended to messages
    ↓
Loop continues until stop_reason != "tool_use"
    ↓
Response streamed to UI
```

### ohmo Gateway Flow
```
Chat Platform (Slack/Telegram/Discord/Feishu)
    ↓
ChannelManager (channels/impl/)
    ↓
MessageBus (channels/bus/)
    ↓
OhmoGatewayBridge
    ↓
OhmoSessionRuntimePool → OpenHarness QueryEngine
    ↓
Response via MessageBus back to channel
```

### Configuration Flow
```
~/.openharness/settings.json
    ↓
load_settings() (config/settings.py)
    ↓
PermissionSettings, GeneralSettings, etc.
    ↓
Injected into QueryEngine, PermissionChecker, etc.
```

---

## 7. Configuration

### Settings Hierarchy
```python
# config/settings.py defines:
- PermissionSettings (mode, path_rules, denied_commands)
- GeneralSettings (model, max_turns, etc.)
- MCPSettings (servers)
- PluginSettings
- ProviderSettings (API keys, base URLs)
```

### Configuration Locations
- **Project-level**: `.openharness/settings.json` in project root
- **User-level**: `~/.openharness/settings.json`
- **Environment variables**: `OPENHARNESS_*` overrides
- **Provider profiles**: Stored separately, selectable via `oh provider use <profile>`

### Provider Profile System
```bash
oh setup              # Interactive provider wizard
oh provider list      # Show available providers
oh provider use <profile>  # Switch active provider
```

Supports:
- Anthropic-Compatible API (Claude, Kimi, GLM, MiniMax)
- Claude Subscription (via bridge)
- OpenAI-Compatible API (OpenAI, OpenRouter, DeepSeek, etc.)
- Codex Subscription
- GitHub Copilot (OAuth device flow)
- Ollama (local models)

### ohmo Workspace Structure (`~/.ohmo/`)
```
~/.ohmo/
├── soul.md           # Agent personality
├── identity.md       # Agent identity
├── user.md           # User profile
├── memory/           # Persistent memory
├── gateway.json      # Provider + channel config
├── gateway.pid       # PID file
└── logs/             # Gateway logs
```

---

## Summary

OpenHarness is a **layered, plugin-extensible agent harness** that provides:

1. **Core Agent Loop**: Streaming tool-call cycle with permission checking, hooks, and auto-compaction
2. **43+ Tools**: File I/O, shell, search, web, MCP, tasks, cron, skills
3. **Multi-Provider Support**: Abstraction over Anthropic, OpenAI, Codex, Copilot, and compatible endpoints
4. **Skills & Plugins**: On-demand knowledge loading and CLI plugin ecosystem
5. **Multi-Agent Coordination**: Subagent spawning, team management, background tasks
6. **Chat Platform Integration**: Gateway service for Slack, Discord, Telegram, Feishu, etc.
7. **Security**: Multi-level permissions, sensitive path protection, hook lifecycle
8. **Terminal UI**: React/Ink TUI for interactive sessions
9. **Personal Agent (ohmo)**: Long-running agent app with its own workspace

The architecture is research-oriented and designed for **understandability, experimentation, and extension** rather than being a black-box commercial product.
