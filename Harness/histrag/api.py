"""Anthropic API client for HistRAG."""

from __future__ import annotations

import asyncio
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


@dataclass
class ApiMessageCompleteEvent:
    """Terminal event containing the full assistant message."""

    content: str
    stop_reason: str | None = None


class AnthropicApiClient:
    """Simple Anthropic API client with streaming support."""

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
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

        try:
            async with self._client.messages.stream(**params) as stream:
                async for event in stream:
                    if getattr(event, "type", None) == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        if getattr(delta, "type", None) == "text_delta":
                            text = getattr(delta, "text", "")
                            if text:
                                yield ApiTextDeltaEvent(text=text)
                    elif getattr(event, "type", None) == "content_block_start":
                        block = getattr(event, "content_block", None)
                        if getattr(block, "type", None) == "tool_use":
                            name = getattr(block, "name", "")
                            input_json = getattr(block, "input", "{}")
                            yield ApiToolUseEvent(name=name, input=input_json)
                    elif getattr(event, "type", None) == "message_delta":
                        stop_reason = getattr(event, "stop_reason", None)
                        yield ApiMessageCompleteEvent(
                            content="",
                            stop_reason=stop_reason,
                        )
        except Exception as e:
            raise


__all__ = [
    "AnthropicApiClient",
    "ApiMessageRequest",
    "ApiTextDeltaEvent",
    "ApiToolUseEvent",
    "ApiMessageCompleteEvent",
]