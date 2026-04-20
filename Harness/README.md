# HistRAG - Historical Research Agent

基于 **OpenHarness** (Agent 框架) + **LightRAG** (知识图谱) 的历史研究 Agent。

## 核心架构

```
histrag CLI (Typer)
    │
    ▼
openharness.ui.runtime.build_runtime()
    │
    ├── API Client (Anthropic/OpenAI)
    ├── ToolRegistry (create_default_tool_registry + 历史工具)
    ├── SkillRegistry (histrag skills 目录)
    ├── PermissionChecker (read-only 模式)
    └── QueryEngine (system_prompt=历史学家提示)
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

## 关键集成点

### 1. `integration.py` - 与 OpenHarness 的集成胶水

```python
from histrag.integration import create_historical_runtime, run_historical_query

# 创建完整 Runtime
runtime = create_historical_runtime(cwd=".", model="claude-sonnet-4-20250514")
await runtime.rag_client.initialize()

# 使用 Agent
async for event in runtime.engine.submit_message("分析秦始皇的因果链"):
    print(event)

await runtime.rag_client.finalize()
```

### 2. Tools - 历史工具注册

```python
from histrag.tools import create_historical_tool_registry

# 历史工具优先级最高，覆盖同名工具
hist_registry = create_historical_tool_registry(rag_client)
for name, tool in hist_registry._tools.items():
    base_registry._tools[name] = tool
```

### 3. Skills - 技能加载

```python
from histrag.skills.loader import load_historical_skill_registry

# 加载编年法、比较法、反事实分析、年鉴学派
registry = load_historical_skill_registry(cwd=".")
```

## 使用方法

### 安装

```bash
cd /home/selom/projects/literag/Harness
pip install -e .
```

### CLI 命令

```bash
# Agent 模式（完整工具调用）
python -m histrag query "分析秦始皇统一六国的因果链"

# 直接 RAG 模式（快速查询）
python -m histrag lightrag "秦始皇的功过"

# 交互模式
python -m histrag interactive

# 查看工具列表
python -m histrag tools

# 版本
python -m histrag version-cmd
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

## 目录结构

```
Harness/
├── histrag/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py              # CLI 入口 (Typer)
│   ├── integration.py      # OpenHarness 集成胶水 (关键)
│   │
│   ├── tools/
│   │   ├── kg_query_tool.py   # 知识图谱查询工具
│   │   ├── rag_query_tool.py  # RAG 查询工具
│   │   ├── cite_tool.py       # 引用溯源工具
│   │   └── registry.py        # 工具注册函数
│   │
│   ├── skills/
│   │   ├── loader.py          # 技能加载器
│   │   ├── chronology.md        # 编年法
│   │   ├── comparison.md       # 比较法
│   │   ├── counterfactual.md   # 反事实分析
│   │   └── annales.md          # 年鉴学派
│   │
│   ├── prompts/
│   │   └── historian.py        # 历史学家系统提示
│   │
│   ├── ohmo/
│   │   ├── soul.md            # Historian 个性
│   │   ├── identity.md        # Historian 身份
│   │   └── memory/
│   │       └── credibility_guide.md  # 来源可信度指南
│   │
│   ├── lightrag/
│   │   ├── client.py          # LightRAG 异步客户端
│   │   ├── types.py           # 数据类型
│   │   └── credibility.py     # 可信度标注层
│   │
│   └── coordinator/
│       └── historian.py        # 2-agent 协调器
│
└── pyproject.toml
```

## 历史工具说明

| 工具 | 说明 |
|------|------|
| `kg_query` | 知识图谱查询：实体查询、模糊搜索、关系路径 |
| `rag_query` | RAG 查询：使用 LLM 生成回答 |
| `rag_data_query` | RAG 数据查询：返回结构化结果（无 LLM） |
| `cite` | 引用管理：插入引用、追溯来源、列出引用 |

## 来源可信度标注

历史研究中信息来源分为三类：

- **[一手文献]** (Primary Source) - 当时文献，如《史记》、《汉书》
- **[二手研究]** (Secondary Source) - 后世研究，如学术专著
- **[争议性说法]** (Disputed) - 存在争议的解读

## 继承自 OpenHarness

- ✅ QueryEngine 核心循环（流式工具调用）
- ✅ Skills 系统（按需加载 .md 技能文件）
- ✅ Memory 系统（会话上下文存储）
- ✅ Permissions 系统（read-only 模式）
- ✅ API Layer（多模型支持）

## 已移除模块

- ❌ Channels（Slack/Discord/Telegram）
- ❌ Autopilot
- ❌ Sandbox
- ❌ Vim/Keybindings/TUI
- ❌ Complex Swarm（使用简化版 Coordinator）
