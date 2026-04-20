"""Historical research tools for the agent."""

from ..agent import BaseTool, ToolExecutionContext, ToolResult, ToolRegistry

from .cite_tool import CiteInput, CiteTool
from .kg_query_tool import KGOperation, KGQueryInput, KGQueryTool
from .rag_query_tool import (
    RAGDataQueryInput,
    RAGDataQueryTool,
    RAGMode,
    RAGQueryInput,
    RAGQueryTool,
)
from .registry import create_historical_tool_registry

__all__ = [
    "BaseTool",
    "ToolExecutionContext",
    "ToolResult",
    "ToolRegistry",
    "KGQueryTool",
    "KGQueryInput",
    "KGOperation",
    "CiteTool",
    "CiteInput",
    "RAGQueryTool",
    "RAGQueryInput",
    "RAGMode",
    "RAGDataQueryTool",
    "RAGDataQueryInput",
    "create_historical_tool_registry",
]
