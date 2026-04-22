"""HistRAG Web Server - 历史研究 Web 界面后端。

提供：
- 静态文件服务（地图资源、前端页面）
- SSE 流式接口：GET /api/query?q=... → 实时推送终端事件
- linked_view HTML 缓存接口：GET /api/view/latest
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# ── 路径常量 ──────────────────────────────────────────────────
HERE          = Path(__file__).parent          # = hHarness/frontend/
RESOURCES_DIR = HERE.parent / "Harness" / "histrag" / "resources"
FRONTEND_DIR  = HERE
WEB_DIR       = HERE

app = FastAPI(title="HistRAG", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 静态资源 ──────────────────────────────────────────────────
if RESOURCES_DIR.exists():
    app.mount("/resources", StaticFiles(directory=str(RESOURCES_DIR)), name="resources")

if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")

# ── 内存缓存最新 linked_view HTML ─────────────────────────────
_latest_view_html: str = ""
_latest_view_lock = asyncio.Lock()


async def _set_latest_view(html: str) -> None:
    global _latest_view_html
    async with _latest_view_lock:
        _latest_view_html = html


@app.get("/api/view/latest", response_class=HTMLResponse)
async def get_latest_view():
    """返回最新的联动视图 HTML。"""
    if not _latest_view_html:
        return HTMLResponse(
            "<html><body style='font-family:serif;color:#888;padding:40px'>"
            "尚无视图，请先发起一次查询。</body></html>"
        )
    return HTMLResponse(_latest_view_html)


# ── SSE 流式查询接口 ───────────────────────────────────────────
@app.get("/api/query")
async def query_stream(q: str):
    """
    SSE 端点：实时推送查询过程中的所有事件。

    事件格式（JSON Lines over SSE）：
      data: {"type": "text_delta",   "text": "..."}
      data: {"type": "tool_start",   "tool": "rag_query"}
      data: {"type": "tool_end",     "tool": "rag_query", "result": "..."}
      data: {"type": "linked_view",  "url": "/api/view/latest"}
      data: {"type": "turn_complete","content": "..."}
      data: {"type": "error",        "message": "..."}
      data: {"type": "done"}
    """

    async def event_stream():
        try:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent / "Harness"))

            from histrag.integration import create_historical_runtime
            from histrag.agent.events import (
                AssistantTextDelta,
                ToolExecutionStarted,
                ToolExecutionCompleted,
                AssistantTurnComplete,
                ErrorEvent,
            )   

            runtime = create_historical_runtime(
                model=os.environ.get("HISTRAG_MODEL", "claude-sonnet-4-20250514"),
                max_turns=int(os.environ.get("HISTRAG_MAX_TURNS", "8")),
            )
            await runtime.rag_client.initialize()

            try:
                async for event in runtime.engine.submit_message(q):
                    if isinstance(event, AssistantTextDelta):
                        yield _sse({"type": "text_delta", "text": event.text})

                    elif isinstance(event, ToolExecutionStarted):
                        yield _sse({"type": "tool_start", "tool": event.tool_name})

                    elif isinstance(event, ToolExecutionCompleted):
                        if event.tool_name == "linked_view" and event.metadata:
                            html = event.metadata.get("html", "")
                            if html:
                                await _set_latest_view(html)
                                yield _sse({
                                    "type": "linked_view",
                                    "url": "/api/view/latest",
                                })
                        else:
                            yield _sse({
                                "type": "tool_end",
                                "tool": event.tool_name,
                                "is_error": event.is_error,
                                "result": (event.result or "")[:300],
                            })

                    elif isinstance(event, AssistantTurnComplete):
                        yield _sse({"type": "turn_complete", "content": event.content})

                    elif isinstance(event, ErrorEvent):
                        yield _sse({"type": "error", "message": event.error})

            finally:
                await runtime.rag_client.finalize()

        except Exception as e:
            yield _sse({"type": "error", "message": str(e)})

        yield _sse({"type": "done"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# ── 主页 ──────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    """返回主 Web UI 页面。"""
    ui_path = WEB_DIR / "index.html"
    if ui_path.exists():
        return HTMLResponse(ui_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>HistRAG UI not found. Run the build step first.</h1>")


# ── 启动入口 ──────────────────────────────────────────────────
def serve(host: str = "0.0.0.0", port: int = 7860, reload: bool = False):
    import uvicorn
    uvicorn.run(
        "histrag.server:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    serve()
