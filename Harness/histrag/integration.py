"""HistRAG - Standalone Agent Runtime without OpenHarness dependency."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator

from .agent.engine import AgentEngine
from .lightrag import LightRAGClient
from .prompts.historian import build_historian_system_prompt
from .tools.registry import create_historical_tool_registry


@dataclass
class HistorianRuntime:
    """历史学家 Agent Runtime 包裹器。"""
    engine: AgentEngine
    rag_client: LightRAGClient
    tool_registry: Any  # ToolRegistry
    skills_dir: Path | None = None
    memory_dir: Path | None = None


# ── 自动下载 Three.js / GSAP / 地图数据 ───────────────────────
def _ensure_resources() -> None:
    """
    检查 resources/lib/ 下是否存在 Three.js 和 GSAP。
    如果不存在，自动执行 setup.sh 下载。
    只在首次启动时运行一次，后续通过 .resources_ready 标记跳过。
    """
    resources_dir = Path(__file__).parent / "resources"
    lib_dir       = resources_dir / "lib"
    flag_file     = resources_dir / ".resources_ready"

    # 已经下载过，跳过
    if flag_file.exists():
        return

    required = ["three.min.js", "gsap.min.js"]
    missing  = [f for f in required if not (lib_dir / f).exists()]

    if not missing:
        # 文件已存在，写入标记
        flag_file.write_text("ok\n")
        return

    setup_sh = resources_dir / "setup.sh"
    if not setup_sh.exists():
        print(
            f"[HistRAG] ⚠️  resources/lib/ 缺少 Three.js/GSAP，"
            f"且 setup.sh 不存在，3D 地图可能无法加载。",
            file=sys.stderr,
        )
        return

    print(
        f"[HistRAG] 首次启动：自动下载 3D 地图资源（{', '.join(missing)}）…",
        flush=True,
    )
    try:
        result = subprocess.run(
            ["bash", str(setup_sh)],
            cwd=str(resources_dir),
            capture_output=False,
            timeout=120,
        )
        if result.returncode == 0:
            flag_file.write_text("ok\n")
            print("[HistRAG] ✓ 资源下载完成", flush=True)
        else:
            print(
                f"[HistRAG] ⚠️  setup.sh 退出码 {result.returncode}，"
                f"3D 地图将使用 CDN fallback",
                file=sys.stderr,
            )
    except subprocess.TimeoutExpired:
        print("[HistRAG] ⚠️  资源下载超时（120s），3D 地图将使用 CDN fallback", file=sys.stderr)
    except Exception as e:
        print(f"[HistRAG] ⚠️  资源下载失败: {e}，3D 地图将使用 CDN fallback", file=sys.stderr)


def create_historical_runtime(
    *,
    cwd: str | Path = ".",
    model: str = "claude-sonnet-4-20250514",
    max_turns: int = 8,
    max_tokens: int = 4096,
    system_prompt: str | None = None,
    api_client: Any = None,
    rag_working_dir: str | Path | None = None,
    rag_config_path: str | Path | None = None,
    extra_skill_dirs: list[str] | Path | None = None,
    extra_memory_dirs: list[str] | Path | None = None,
    **kwargs: Any,
) -> HistorianRuntime:
    """Create historical agent runtime.

    This function:
    1. Ensures Three.js / GSAP resources are downloaded (auto on first run)
    2. Initializes LightRAG Client
    3. Builds historian system prompt from ohmo/ files
    4. Creates tool registry with historical tools
    5. Creates AgentEngine
    6. Sets up skills and memory directories
    """
    # ── 0. 确保 3D 地图资源就绪 ──────────────────────────────
    _ensure_resources()

    cwd = Path(cwd).resolve()

    # Determine skills directory
    if extra_skill_dirs:
        if isinstance(extra_skill_dirs, (str, Path)):
            skills_dir = Path(extra_skill_dirs)
        else:
            skills_dir = Path(extra_skill_dirs[0])
    else:
        skills_dir = Path(__file__).parent.parent / "skills"

    # Determine memory directory
    if extra_memory_dirs:
        if isinstance(extra_memory_dirs, (str, Path)):
            memory_dir = Path(extra_memory_dirs)
        else:
            memory_dir = Path(extra_memory_dirs[0])
    else:
        memory_dir = Path(__file__).parent.parent / "ohmo" / "memory"

    # 1. Initialize LightRAG Client
    if rag_config_path is None:
        for path in [
            Path(__file__).parent.parent / "rag_config.yaml",
        ]:
            if path.exists():
                rag_config_path = path
                break

    config = None
    if rag_config_path:
        from .lightrag.config import create_lightrag_from_config

        rag, config = create_lightrag_from_config(rag_config_path)
        rag_client = LightRAGClient(
            working_dir=rag.working_dir,
            _rag=rag,
        )
    elif rag_working_dir:
        rag_client = LightRAGClient(working_dir=rag_working_dir)
    else:
        rag_client = LightRAGClient(
            working_dir=Path.home() / ".histrag" / "rag_storage"
        )

    # 2. Build historian system prompt
    if system_prompt is None:
        system_prompt = build_historian_system_prompt(
            cwd=cwd,
            include_skills=True,
            include_memory=True,
        )

    # 3. Create API client if not provided
    if api_client is None:
        from .api import AnthropicApiClient

        if config:
            llm_config = config.get("llm", {})
            api_key  = llm_config.get("api_key")
            base_url = llm_config.get("base_url")
            model    = llm_config.get("model_name", model)
            api_client = AnthropicApiClient(api_key=api_key, base_url=base_url)
        else:
            api_client = AnthropicApiClient()

    # 4. Create tool registry
    tool_registry = create_historical_tool_registry(rag_client)

    # 5. Create AgentEngine
    engine = AgentEngine(
        api_client=api_client,
        tool_registry=tool_registry,
        system_prompt=system_prompt,
        model=model,
        max_turns=max_turns,
        cwd=str(cwd),
    )

    return HistorianRuntime(
        engine=engine,
        rag_client=rag_client,
        tool_registry=tool_registry,
        skills_dir=skills_dir if skills_dir.exists() else None,
        memory_dir=memory_dir if memory_dir.exists() else None,
    )


async def run_historical_query(
    prompt: str,
    *,
    cwd: str | Path = ".",
    model: str = "claude-sonnet-4-20250514",
    max_turns: int = 8,
    **kwargs: Any,
) -> AsyncIterator[Any]:
    """Run historical query - async generator yields StreamEvents."""
    runtime = create_historical_runtime(
        cwd=cwd,
        model=model,
        max_turns=max_turns,
        **kwargs,
    )

    await runtime.rag_client.initialize()

    try:
        async for event in runtime.engine.submit_message(prompt):
            yield event
    finally:
        await runtime.rag_client.finalize()


# Memory management functions
def get_memory_dir() -> Path:
    """Get the HistRAG memory directory."""
    return Path.home() / ".histrag" / "memory"


def load_project_memory(cwd: str | Path | None = None) -> str | None:
    """Load memory content for display to the user."""
    memory_dir = get_memory_dir()

    if cwd:
        from hashlib import sha1
        path   = Path(cwd).resolve()
        digest = sha1(str(path).encode("utf-8")).hexdigest()[:12]
        memory_dir = memory_dir / f"{path.name}-{digest}"

    memory_dir.mkdir(parents=True, exist_ok=True)
    memory_index = memory_dir / "MEMORY.md"

    if memory_index.exists():
        return memory_index.read_text(encoding="utf-8")
    return None


def add_memory_entry(cwd: str | Path | None, title: str, content: str) -> Path:
    """Add a memory entry to the project memory."""
    import re

    memory_dir = get_memory_dir()

    if cwd:
        from hashlib import sha1
        path   = Path(cwd).resolve()
        digest = sha1(str(path).encode("utf-8")).hexdigest()[:12]
        memory_dir = memory_dir / f"{path.name}-{digest}"

    memory_dir.mkdir(parents=True, exist_ok=True)

    slug = re.sub(r"[^a-zA-Z0-9]+", "_", title.strip().lower()).strip("_") or "memory"
    memory_path = memory_dir / f"{slug}.md"
    memory_path.write_text(content.strip() + "\n", encoding="utf-8")

    memory_index = memory_dir / "MEMORY.md"
    existing = memory_index.read_text(encoding="utf-8") if memory_index.exists() else "# Memory Index\n"
    if memory_path.name not in existing:
        existing = existing.rstrip() + f"- [{title}]({memory_path.name})\n"
        memory_index.write_text(existing, encoding="utf-8")

    return memory_path


__all__ = [
    "HistorianRuntime",
    "create_historical_runtime",
    "run_historical_query",
    "get_memory_dir",
    "load_project_memory",
    "add_memory_entry",
]