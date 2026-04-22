"""Anthropic API client for HistRAG."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, AsyncIterator

import anthropic


@dataclass
class ApiMessageRequest:
    """Input parameters for a model invocation."""

    model: str
    messages: list[dict[str, Any]]
    system_prompt: str | None = None
    max_tokens: int = 4096
    tools: list[dict[str, Any]] | None = None


@dataclass
class ApiTextDeltaEvent:
    """Incremental text produced by the model."""

    text: str


@dataclass
class ApiToolUseEvent:
    """Tool use from the model."""

    name: str
    input: dict[str, Any]
    tool_call_id: str = ""


@dataclass
class ApiMessageCompleteEvent:
    """Terminal event containing the full assistant message."""

    content: str
    stop_reason: str | None = None


class AnthropicApiClient:
    """Simple Anthropic API client with streaming support."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("MINIMAX_API_KEY")
        if not self._api_key:
            raise ValueError("ANTHROPIC_API_KEY or MINIMAX_API_KEY not set")
        if base_url:
            self._client = anthropic.AsyncAnthropic(
                api_key=self._api_key,
                base_url=base_url,
            )
        else:
            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)

    async def stream_message(self, request: ApiMessageRequest) -> AsyncIterator[Any]:
        """Yield streamed events for the request."""
        params: dict[str, Any] = {
            "model": request.model,
            "messages": request.messages,
            "max_tokens": request.max_tokens,
        }
        if request.system_prompt:
            params["system"] = request.system_prompt
        if request.tools:
            params["tools"] = request.tools

        # 标识这次请求的身份，方便日志区分
        tool_names = [t.get("name","?") for t in (request.tools or [])]
        req_label = f"[tools={tool_names}]" if tool_names else "[no-tools]"
        msg_count = len(request.messages)
        last_msg_preview = str(request.messages[-1])[:80] if request.messages else ""
        print(f"[API] stream_message START {req_label} msgs={msg_count} last={last_msg_preview!r}", flush=True)

        # Map tool_call_id -> partial JSON from input_json events
        pending_tool_inputs: dict[str, str] = {}
        # Most recently seen tool_call_id (set during content_block_start of tool_use)
        last_tool_call_id: str | None = None
        event_count = 0

        try:
            async with self._client.messages.stream(**params) as stream:
                async for event in stream:
                    event_count += 1
                    event_type = getattr(event, "type", None)

                    if event_type == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        delta_type = getattr(delta, "type", None)
                        if delta_type == "text_delta":
                            text = getattr(delta, "text", "")
                            if text:
                                yield ApiTextDeltaEvent(text=text)

                    elif event_type == "input_json":
                        # MiniMax: InputJsonEvent with partial_json and snapshot
                        # The tool_call_id may be empty, so we track via last_tool_call_id
                        partial = getattr(event, "partial_json", "")
                        tool_call_id = getattr(event, "tool_call_id", "") or last_tool_call_id or ""
                        if tool_call_id and partial:
                            pending_tool_inputs[tool_call_id] = partial
                            print(f"[DEBUG] input_json: tool_call_id={tool_call_id}, partial={partial}", flush=True)

                    elif event_type == "content_block_start":
                        block = getattr(event, "content_block", None)
                        if getattr(block, "type", None) == "tool_use":
                            last_tool_call_id = getattr(block, "id", "")
                            print(f"[DEBUG] content_block_start tool_use: id={last_tool_call_id}", flush=True)
                        elif getattr(block, "type", None) == "text":
                            last_tool_call_id = None  # Reset on non-tool blocks

                    elif event_type == "content_block_stop":
                        block = getattr(event, "content_block", None)
                        if getattr(block, "type", None) == "tool_use":
                            tool_call_id = getattr(block, "id", "")
                            name = getattr(block, "name", "")
                            input_json = getattr(block, "input", {})
                            # Override with buffered partial if it has more complete data
                            if tool_call_id in pending_tool_inputs:
                                try:
                                    import json
                                    buffered = json.loads(pending_tool_inputs[tool_call_id])
                                    # Merge: buffered takes precedence if it has actual values
                                    if buffered.get("query") is not None:
                                        input_json = buffered
                                except Exception:
                                    pass
                                del pending_tool_inputs[tool_call_id]
                            print(f"[DEBUG] content_block_stop tool_use: id={tool_call_id}, name={name}, input={input_json}", flush=True)
                            yield ApiToolUseEvent(name=name, input=input_json, tool_call_id=tool_call_id)

                    elif event_type == "message_delta":
                        stop_reason = getattr(event, "stop_reason", None)
                        print(f"[API] stream_message DONE {req_label} events={event_count} stop_reason={stop_reason}", flush=True)
                        yield ApiMessageCompleteEvent(content="", stop_reason=stop_reason)

        except Exception as e:
            print(f"[API] stream_message ERROR {req_label} after {event_count} events: {type(e).__name__}: {e}", flush=True)
            raise


__all__ = [
    "AnthropicApiClient",
    "ApiMessageRequest",
    "ApiTextDeltaEvent",
    "ApiToolUseEvent",
    "ApiMessageCompleteEvent",
]