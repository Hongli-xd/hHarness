"""Backward-compatible map location tool wrapper.

Map rendering is now handled by LinkedViewTool. This module keeps the old import
path available for callers and tests that only need the read-only tool contract.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..agent import BaseTool, ToolExecutionContext, ToolResult


class MapLocationInput(BaseModel):
    places: list[dict] = Field(default_factory=list)


class MapLocationTool(BaseTool):
    name = "map_location"
    description = "Compatibility wrapper for historical map location rendering."
    input_model = MapLocationInput

    async def execute(
        self,
        arguments: MapLocationInput,
        context: ToolExecutionContext,
    ) -> ToolResult:
        return ToolResult(
            output="MapLocationTool is deprecated; use linked_view instead.",
            metadata={"places": arguments.places, "type": "map_location"},
        )
