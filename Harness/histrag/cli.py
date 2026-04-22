"""HistRAG CLI - Standalone Historical Research Agent."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown

from .integration import create_historical_runtime
from .lightrag import LightRAGClient
from lightrag import QueryParam

app = typer.Typer(name="histrag", help="HistRAG - Historical Research Agent", add_completion=False)
console = Console()

DEFAULT_WORKING_DIR = Path.home() / ".histrag" / "rag_storage"


@app.command()
def query(
    question: str = typer.Argument(..., help="Historical research question"),
    cwd: Path = typer.Option(".", "--cwd", "-C"),
    model: str = typer.Option("claude-sonnet-4-20250514", "--model", "-m"),
    max_turns: int = typer.Option(8, "--max-turns", "-n"),
) -> None:
    """Query using the full Agent with tools."""
    from .agent.events import (
        AssistantTextDelta,
        ToolExecutionStarted,
        ToolExecutionCompleted,
        AssistantTurnComplete,
    )

    console.print(f"[bold blue]Question:[/bold blue] {question}")
    console.print(f"[dim]Model:[/dim] {model} | [dim]Max turns:[/dim] {max_turns}\n")

    async def _run():
        runtime = create_historical_runtime(
            cwd=cwd,
            model=model,
            max_turns=max_turns,
        )

        await runtime.rag_client.initialize()

        try:
            async for event in runtime.engine.submit_message(question):
                if isinstance(event, AssistantTextDelta):
                    print(event.text, end="", flush=True)
                elif isinstance(event, ToolExecutionStarted):
                    print(f"\n[[TOOL: {event.tool_name}]]")
                elif isinstance(event, ToolExecutionCompleted):
                    if event.is_error:
                        print(f"[[TOOL ERROR: {event.tool_name}]]")
                        print(f"{event.result}")
                    else:
                        print(f"[[/TOOL: {event.tool_name}]]")
                        if event.result:
                            print(event.result)
                elif isinstance(event, AssistantTurnComplete):
                    console.print("\n")
        finally:
            await runtime.rag_client.finalize()

    asyncio.run(_run())


@app.command()
def lightrag(
    question: str = typer.Argument(..., help="Query for LightRAG (direct RAG, no agent)"),
    config_path: Path = typer.Option(None, "--config", "-c"),
    mode: str = typer.Option("mix", "--mode"),
) -> None:
    """Direct LightRAG query without full agent."""
    from .lightrag.config import create_lightrag_from_config

    console.print(f"[bold blue]Question:[/bold blue] {question}")
    console.print(f"[dim]Mode:[/dim] {mode}\n")

    if config_path is None:
        for path in [
            Path.cwd() / "rag_config.yaml",
            Path(__file__).parent.parent / "rag_config.yaml",
        ]:
            if path.exists():
                config_path = path
                break

    async def _run():
        rag, _ = create_lightrag_from_config(config_path)
        await rag.initialize_storages()

        try:
            result = await rag.aquery(question, param=QueryParam(mode=mode))
            console.print(Markdown(f"**Response:**\n\n{result}"))
        finally:
            await rag.finalize_storages()

    asyncio.run(_run())


@app.command()
def interactive(
    cwd: Path = typer.Option(".", "--cwd", "-C"),
    model: str = typer.Option("claude-sonnet-4-20250514", "--model", "-m"),
) -> None:
    """Start interactive historical research session."""
    console.print("[bold blue]HistRAG - Historical Research Agent[/bold blue]")
    console.print("[dim]Type 'exit' or 'quit' to end, 'clear' to clear history[/dim]\n")

    async def _run():
        runtime = create_historical_runtime(
            cwd=cwd, model=model, max_turns=20, rag_working_dir=DEFAULT_WORKING_DIR,
        )

        await runtime.rag_client.initialize()

        try:
            message_count = 0
            while True:
                try:
                    question = console.input("[bold green]>[/bold green] ")
                    if question.lower() in {"exit", "quit", "q"}:
                        break
                    if question.lower() == "clear":
                        runtime.engine.clear()
                        console.print("[dim]History cleared[/dim]\n")
                        continue
                    if not question.strip():
                        continue

                    message_count += 1
                    console.print(f"\n[dim]Turn {message_count}...[/dim]\n")

                    from .agent.events import (
                        AssistantTextDelta,
                        ToolExecutionStarted,
                        ToolExecutionCompleted,
                        AssistantTurnComplete,
                    )

                    async for event in runtime.engine.submit_message(question):
                        if isinstance(event, AssistantTextDelta):
                            print(event.text, end="", flush=True)
                        elif isinstance(event, ToolExecutionStarted):
                            console.print(f"\n[cyan][[TOOL: {event.tool_name}]][/cyan]")
                        elif isinstance(event, ToolExecutionCompleted):
                            if event.is_error:
                                console.print(f"[red][[/TOOL ERROR: {event.tool_name}]][/red]")
                            else:
                                console.print(f"[cyan][[/TOOL: {event.tool_name}]][/cyan]")
                        elif isinstance(event, AssistantTurnComplete):
                            console.print("\n")

                except KeyboardInterrupt:
                    break
                except Exception as e:
                    console.print(f"[red]Error: {e}[/red]")

        finally:
            await runtime.rag_client.finalize()

    asyncio.run(_run())
    console.print("\n[blue]Goodbye![/blue]")


@app.command()
def setup(
    working_dir: Path = typer.Option(DEFAULT_WORKING_DIR, "--working-dir", "-d"),
) -> None:
    """Setup HistRAG configuration."""
    console.print("[bold]Setting up HistRAG...[/bold]\n")
    working_dir.mkdir(parents=True, exist_ok=True)

    histrag_ohmo = Path(__file__).parent / "ohmo"
    console.print(f"HistRAG ohmo workspace: {histrag_ohmo}")
    console.print("\n[bold green]Setup complete![/bold green]")
    console.print(f"\nLightRAG storage: {working_dir}")


@app.command()
def version_cmd() -> None:
    """Show HistRAG version."""
    from . import __version__
    console.print(f"HistRAG v{__version__}")


@app.command()
def create_graph(
    input_file: Path = typer.Argument(..., help="Input text file to create knowledge graph"),
    config_path: Path = typer.Option(None, "--config", "-c"),
    chunk_token_size: int = typer.Option(1200, "--chunk-size"),
    chunk_overlap: int = typer.Option(100, "--overlap"),
) -> None:
    """Create knowledge graph from input document(s).

    Reads a text file and indexes it into the knowledge graph storage.
    Supports Neo4j, vector storage, and graph extraction.
    """
    from .lightrag.config import create_lightrag_from_config

    console.print(f"[bold blue]Creating knowledge graph from:[/bold blue] {input_file}")

    if not input_file.exists():
        console.print(f"[red]Error: File not found: {input_file}[/red]")
        raise typer.Exit(1)

    # Find config
    if config_path is None:
        for path in [
            Path.cwd() / "rag_config.yaml",
            Path(__file__).parent.parent / "rag_config.yaml",
        ]:
            if path.exists():
                config_path = path
                break

    if config_path is None:
        console.print("[red]Error: No config file found. Use --config or place rag_config.yaml in project root.[/red]")
        raise typer.Exit(1)

    console.print(f"[dim]Using config:[/dim] {config_path}")

    async def _run():
        rag, config = create_lightrag_from_config(config_path)
        await rag.initialize_storages()

        try:
            with open(input_file, "r", encoding="utf-8") as f:
                text = f.read()

            console.print(f"[dim]Indexing {len(text)} characters...[/dim]")
            await rag.ainsert(text)
            console.print("[bold green]Knowledge graph created successfully![/bold green]")
        finally:
            await rag.finalize_storages()

    asyncio.run(_run())


@app.command()
def tools() -> None:
    """List available historical research tools."""
    console.print("[bold]Historical Research Tools:[/bold]\n")
    console.print("  rag_query    - Full RAG query with LLM")
    console.print("  rag_data_query - RAG data only (no LLM)")
    console.print("  cite         - Citation and source tracing")

@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-H"),
    port: int = typer.Option(7860, "--port", "-p"),
    reload: bool = typer.Option(False, "--reload"),
) -> None:
    """启动 Web UI 服务器，浏览器访问 http://localhost:{port}"""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]需要安装 uvicorn：pip install uvicorn[standard][/red]")
        raise typer.Exit(1)
 
    console.print(f"[bold green]HistRAG Web UI[/bold green] 启动中…")
    console.print(f"  → [link=http://localhost:{port}]http://localhost:{port}[/link]")
    uvicorn.run(
        "frontend.server:app",
        host=host,
        port=port,
        reload=reload,
    )
 

def main():
    app()


if __name__ == "__main__":
    main()