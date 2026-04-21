"""Tool registry for historical research tools.

This module provides the function to create a complete historical tool registry
that can be merged with OpenHarness's default tool registry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..agent import ToolRegistry

from .cite_tool import CiteTool
from .rag_query_tool import RAGDataQueryTool, RAGQueryTool
from .timeline_tool import TimelineTool
from .map_location_tool import MapLocationTool


def create_historical_tool_registry(
    rag_client,  # LightRAGClient - injected at runtime
) -> "ToolRegistry":
    """Create tool registry with historical research tools.

    IMPORTANT: These tools are designed to be the HIGHEST PRIORITY tools
    in the agent's tool list. When merged with the default OpenHarness registry,
    historical tools should override any tools with the same name.

    Args:
        rag_client: LightRAGClient instance for queries

    Returns:
        ToolRegistry with all historical research tools
    """
    from ..agent import ToolRegistry
    from histrag.lightrag import CredibilityAnnotator

    registry = ToolRegistry()

    # Create annotator for citation tools
    annotator = CredibilityAnnotator()

    # PRIMARY research tools - highest priority
    registry.register(CiteTool(annotator))

    # Secondary research tools
    registry.register(RAGQueryTool(rag_client))
    registry.register(RAGDataQueryTool(rag_client))

    # Visualization tools
    registry.register(TimelineTool())
    registry.register(MapLocationTool())

    return registry


__all__ = [
    "create_historical_tool_registry",
]
