"""Backward-compatible timeline tool wrapper.

Timeline rendering is now handled by LinkedViewTool. This module keeps the old
import path available for callers and tests that only need the read-only tool
contract.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..agent import BaseTool, ToolExecutionContext, ToolResult


class TimelineInput(BaseModel):
    events: list[dict] = Field(default_factory=list)


class TimelineTool(BaseTool):
    name = "timeline"
    description = "Compatibility wrapper for historical timeline rendering."
    input_model = TimelineInput

    async def execute(
        self,
        arguments: TimelineInput,
        context: ToolExecutionContext,
    ) -> ToolResult:
        return ToolResult(
            output="TimelineTool is deprecated; use linked_view instead.",
            metadata={"events": arguments.events, "type": "timeline"},
        )
