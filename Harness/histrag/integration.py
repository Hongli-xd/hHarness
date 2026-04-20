"""HistRAG - Standalone Agent Runtime without OpenHarness dependency."""

from __future__ import annotations

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
    extra_skill_dirs: list[str] | None = None,
    **kwargs: Any,
) -> HistorianRuntime:
    """Create historical agent runtime.

    This function:
    1. Initializes LightRAG Client
    2. Builds historian system prompt
    3. Creates tool registry with historical tools
    4. Creates AgentEngine
    """
    cwd = Path(cwd).resolve()

    # 1. Initialize LightRAG Client
    if rag_config_path:
        from .lightrag.config import create_lightrag_from_config
        rag_client, _ = create_lightrag_from_config(rag_config_path)
    elif rag_working_dir:
        rag_client = LightRAGClient(working_dir=rag_working_dir)
    else:
        rag_client = LightRAGClient(
            working_dir=Path.home() / ".histrag" / "rag_storage"
        )

    # 2. Build historian system prompt
    if system_prompt is None:
        system_prompt = build_historian_system_prompt(cwd=cwd)

    # 3. Create API client if not provided
    if api_client is None:
        from .api import AnthropicApiClient
        api_client = AnthropicApiClient()

    # 4. Create tool registry with historical tools
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


__all__ = [
    "HistorianRuntime",
    "create_historical_runtime",
    "run_historical_query",
]