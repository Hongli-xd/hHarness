"""General RAG Query Tool for historical research.

This tool provides full-text RAG query capabilities using LightRAG,
complementing the KG Query Tool for when you need to search through
the full text corpus.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from ..agent import BaseTool, ToolExecutionContext, ToolResult

from ..lightrag import LightRAGClient


class RAGMode(str, Enum):
    """Query modes for RAG search."""

    LOCAL = "local"  # Context-dependent, specific entities
    GLOBAL = "global"  # Community-based, broad knowledge
    HYBRID = "hybrid"  # Combines local and global
    NAIVE = "naive"  # Direct vector search, no graph
    MIX = "mix"  # KG + vector with reranking (recommended)


class RAGQueryInput(BaseModel):
    """Input schema for the RAG Query Tool."""

    query: str = Field(
        description="Research question or topic to query"
    )
    mode: RAGMode = Field(
        default=RAGMode.MIX,
        description="Query mode: local (specific), global (broad), hybrid, naive (vector only), mix (recommended)"
    )
    top_k: int = Field(
        default=60,
        ge=1,
        le=200,
        description="Number of knowledge graph entities/relations to retrieve"
    )
    chunk_top_k: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of text chunks to retrieve"
    )
    stream: bool = Field(
        default=False,
        description="Whether to stream the LLM response"
    )


class RAGQueryTool(BaseTool):
    """General RAG Query Tool for historical research.

    Provides full-text RAG query capabilities with multiple retrieval modes.
    Use this when you need to search the full text corpus, not just
    entity relationships.

    Modes:
    - mix (recommended): Combines KG and vector retrieval with reranking
    - hybrid: Local + global retrieval
    - local: Context-dependent retrieval for specific entities
    - global: Community-based broad knowledge retrieval
    - naive: Direct vector search without graph
    """

    name = "rag_query"
    description = """Query the historical knowledge base using Retrieval-Augmented Generation.

Use this for full-text research queries that search through the document corpus.

Modes:
- mix (recommended): Combines knowledge graph and vector retrieval with reranking
- hybrid: Combines local (specific) and global (broad) retrieval
- local: Focus on specific entities and their immediate context
- global: Broad retrieval from entity communities
- naive: Direct vector similarity search only

Returns LLM-generated response with citations to source chunks.
"""
    input_model = RAGQueryInput

    def __init__(self, rag_client: LightRAGClient):
        """Initialize RAG Query Tool.

        Args:
            rag_client: LightRAG client for queries
        """
        self.rag_client = rag_client
        super().__init__()

    def is_read_only(self, arguments: RAGQueryInput) -> bool:
        """RAG queries are always read-only."""
        return True

    async def execute(
        self, arguments: RAGQueryInput, context: ToolExecutionContext
    ) -> ToolResult:
        """Execute the RAG query."""
        try:
            result = await self.rag_client.aquery(
                query=arguments.query,
                mode=arguments.mode.value,
                top_k=arguments.top_k,
                chunk_top_k=arguments.chunk_top_k,
                stream=arguments.stream,
            )

            # Handle streaming response
            if arguments.stream:
                # For streaming, accumulate chunks
                chunks = []
                async for chunk in result:
                    chunks.append(chunk)
                output = "".join(chunks)
            else:
                output = str(result)

            return ToolResult(output=output)

        except Exception as e:
            return ToolResult(
                output=f"RAG Query Error: {str(e)}",
                is_error=True,
            )


class RAGDataQueryInput(BaseModel):
    """Input schema for RAG data-only query (no LLM generation)."""

    query: str = Field(
        description="Research question or topic"
    )
    mode: RAGMode = Field(
        default=RAGMode.MIX,
        description="Query mode"
    )
    top_k: int = Field(
        default=60,
        ge=1,
        le=200,
        description="Number of KG entities to retrieve"
    )
    chunk_top_k: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of text chunks to retrieve"
    )


class RAGDataQueryTool(BaseTool):
    """RAG Data Query Tool - returns structured data without LLM generation.

    Use this when you want to retrieve raw context without LLM synthesis,
    useful for when the agent needs to process the raw data itself.
    """

    name = "rag_data_query"
    description = """Query the knowledge base and return structured data without LLM synthesis.

Returns raw entities, relations, and text chunks from the knowledge graph.
Use when you want to process the raw data yourself or need context for analysis.
"""
    input_model = RAGDataQueryInput

    def __init__(self, rag_client: LightRAGClient):
        """Initialize RAG Data Query Tool."""
        self.rag_client = rag_client
        super().__init__()

    def is_read_only(self, arguments: RAGDataQueryInput) -> bool:
        return True

    async def execute(
        self, arguments: RAGDataQueryInput, context: ToolExecutionContext
    ) -> ToolResult:
        """Execute the RAG data query (no LLM)."""
        try:
            result = await self.rag_client.aquery_data(
                query=arguments.query,
                mode=arguments.mode.value,
                top_k=arguments.top_k,
                chunk_top_k=arguments.chunk_top_k,
            )

            # Format the structured result
            output = self._format_rag_data(result)

            return ToolResult(output=output)

        except Exception as e:
            return ToolResult(
                output=f"RAG Data Query Error: {str(e)}",
                is_error=True,
            )

    def _format_rag_data(self, data: dict) -> str:
        """Format structured RAG data for display."""
        lines = ["# RAG Query Results\n"]

        # Entities
        if "entities" in data and data["entities"]:
            lines.append(f"## Entities ({len(data['entities'])})\n")
            for entity in data["entities"][:20]:  # Limit display
                name = entity.get("entity_name", "unknown")
                desc = entity.get("description", "")[:100]
                lines.append(f"- **{name}**: {desc}...")
            if len(data["entities"]) > 20:
                lines.append(f"  ... and {len(data['entities']) - 20} more")

        # Relations
        if "relations" in data and data["relations"]:
            lines.append(f"\n## Relations ({len(data['relations'])})\n")
            for rel in data["relations"][:20]:
                src = rel.get("src_tgt", [rel.get("source", ""), rel.get("target", "")])
                desc = rel.get("description", "")[:80]
                lines.append(f"- {' → '.join(src)}: {desc}...")
            if len(data["relations"]) > 20:
                lines.append(f"  ... and {len(data['relations']) - 20} more")

        # Chunks
        if "chunks" in data and data["chunks"]:
            lines.append(f"\n## Text Chunks ({len(data['chunks'])})\n")
            for i, chunk in enumerate(data["chunks"][:10], 1):
                if isinstance(chunk, dict):
                    text = chunk.get("chunk_text", str(chunk))[:200]
                else:
                    text = str(chunk)[:200]
                lines.append(f"{i}. {text}...")
            if len(data["chunks"]) > 10:
                lines.append(f"\n... and {len(data['chunks']) - 10} more chunks")

        return "\n".join(lines)
