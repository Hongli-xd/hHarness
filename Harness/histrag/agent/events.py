"""Stream events for the Agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class StreamEvent:
    """Base class for stream events."""
    pass


@dataclass
class AssistantTextDelta(StreamEvent):
    """Text delta from assistant."""
    text: str


@dataclass
class AssistantTurnComplete(StreamEvent):
    """Assistant turn completed."""
    content: str


@dataclass
class ToolExecutionStarted(StreamEvent):
    """Tool execution started."""
    tool_name: str
    tool_input: dict[str, Any]


@dataclass
class ToolExecutionCompleted(StreamEvent):
    """Tool execution completed."""
    tool_name: str
    result: str
    is_error: bool = False
    metadata: dict[str, Any] | None = None  # 可携带 html 等附加数据



@dataclass
class ErrorEvent(StreamEvent):
    """Error event."""
    error: str


@dataclass
class CompactProgressEvent(StreamEvent):
    """Context compaction progress."""
    message: str


__all__ = [
    "StreamEvent",
    "AssistantTextDelta",
    "AssistantTurnComplete",
    "ToolExecutionStarted",
    "ToolExecutionCompleted",
    "ErrorEvent",
    "CompactProgressEvent",
]
