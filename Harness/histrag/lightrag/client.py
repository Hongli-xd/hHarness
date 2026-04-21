"""Async wrapper for LightRAG operations."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, AsyncIterator

from lightrag import LightRAG, QueryParam

from .types import (
    EntityInfo,
    KnowledgeGraphResult,
    RelationInfo,
)


class LightRAGClient:
    """Async wrapper for LightRAG operations.

    Provides a clean async interface to LightRAG's knowledge graph
    and RAG query capabilities.
    """

    def __init__(
        self,
        working_dir: str | Path,
        llm_model_func: Any = None,
        embedding_func: Any = None,
        _rag: Any = None,
        **kwargs: Any,
    ):
        """Initialize LightRAG client.

        Args:
            working_dir: Directory for LightRAG storage cache
            llm_model_func: LLM function for queries (required for aquery)
            embedding_func: Embedding function (required for indexing)
            _rag: Existing LightRAG instance (optional, takes ownership)
            **kwargs: Additional arguments passed to LightRAG constructor
        """
        self.working_dir = Path(working_dir)
        self.working_dir.mkdir(parents=True, exist_ok=True)

        if _rag is not None:
            self._rag = _rag
        else:
            self._rag = LightRAG(
                working_dir=str(self.working_dir),
                llm_model_func=llm_model_func,
                embedding_func=embedding_func,
                **kwargs,
            )
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize LightRAG storage backends.

        Must be called before any query or insert operations.
        """
        if not self._initialized:
            await self._rag.initialize_storages()
            self._initialized = True

    async def finalize(self) -> None:
        """Finalize and cleanup storage connections."""
        if self._initialized:
            await self._rag.finalize_storages()
            self._initialized = False

    async def get_entity_info(
        self, entity_name: str, include_vector_data: bool = False
    ) -> EntityInfo:
        """Get detailed information about a historical entity.

        Args:
            entity_name: Name of the entity to query
            include_vector_data: Whether to include vector similarity data

        Returns:
            EntityInfo with all entity attributes
        """
        data = await self._rag.get_entity_info(entity_name, include_vector_data)
        if data is None or data.get("graph_data") is None:
            # Entity not found - return placeholder
            return EntityInfo.from_dict({
                "entity_name": entity_name,
                "entity_type": "未知",
                "description": f"未在知识图谱中找到实体：{entity_name}",
            })
        return EntityInfo.from_dict(data)

    async def get_relation_info(
        self, src_entity: str, tgt_entity: str, include_vector_data: bool = False
    ) -> RelationInfo:
        """Get information about a relationship between two entities.

        Args:
            src_entity: Source entity name
            tgt_entity: Target entity name
            include_vector_data: Whether to include vector similarity data

        Returns:
            RelationInfo with relationship attributes
        """
        data = await self._rag.get_relation_info(src_entity, tgt_entity, include_vector_data)
        return RelationInfo.from_dict(src_entity, tgt_entity, data)

    async def search_labels(self, query: str, limit: int = 50) -> list[str]:
        """Fuzzy search for entity labels.

        Args:
            query: Search query (partial name or description)
            limit: Maximum number of results

        Returns:
            List of matching entity names
        """
        return await self._rag.chunk_entity_relation_graph.search_labels(query, limit)

    async def get_knowledge_graph(
        self, node_label: str, max_depth: int = 3, max_nodes: int = 1000
    ) -> KnowledgeGraphResult:
        """Get a connected subgraph starting from a node.

        Args:
            node_label: Starting entity name
            max_depth: Maximum traversal depth (default 3)
            max_nodes: Maximum number of nodes to return

        Returns:
            KnowledgeGraphResult with nodes and edges
        """
        result = await self._rag.get_knowledge_graph(node_label, max_depth, max_nodes)
        return KnowledgeGraphResult(
            nodes=result.nodes,
            edges=result.edges,
            is_truncated=result.is_truncated,
        )

    async def aquery(
        self,
        query: str,
        mode: str = "mix",
        top_k: int = 60,
        chunk_top_k: int = 20,
        stream: bool = False,
        **kwargs: Any,
    ) -> str | AsyncIterator[str]:
        """Perform a RAG query with LLM generation.

        Args:
            query: Query text
            mode: Query mode (local/global/hybrid/naive/mix/bypass)
            top_k: Number of KG entities/relations to retrieve
            chunk_top_k: Number of text chunks to retrieve
            stream: Whether to stream the response
            **kwargs: Additional QueryParam arguments

        Returns:
            LLM response string, or AsyncIterator if streaming
        """
        param = QueryParam(
            mode=mode,
            top_k=top_k,
            chunk_top_k=chunk_top_k,
            stream=stream,
            **kwargs,
        )
        return await self._rag.aquery(query, param)

    async def aquery_data(
        self,
        query: str,
        mode: str = "mix",
        top_k: int = 60,
        chunk_top_k: int = 20,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Perform a RAG query returning structured retrieval results (no LLM).

        Args:
            query: Query text
            mode: Query mode
            top_k: Number of KG entities/relations to retrieve
            chunk_top_k: Number of text chunks to retrieve
            **kwargs: Additional QueryParam arguments

        Returns:
            Structured dict with entities, relations, chunks
        """
        param = QueryParam(
            mode=mode,
            top_k=top_k,
            chunk_top_k=chunk_top_k,
            **kwargs,
        )
        return await self._rag.aquery_data(query, param)

    async def insert(self, text: str | list[str], **kwargs: Any) -> None:
        """Insert text into the knowledge graph.

        Args:
            text: Text or list of texts to index
            **kwargs: Additional arguments for insert
        """
        await self._rag.ainsert(text, **kwargs)

    async def query_entity_paths(
        self, source_entity: str, target_entity: str, max_depth: int = 3
    ) -> list[list[str]]:
        """Find paths between two entities.

        Uses BFS to find connection paths. Useful for understanding
        how two historical entities are related through intermediaries.

        Args:
            source_entity: Starting entity
            target_entity: Target entity
            max_depth: Maximum path length

        Returns:
            List of paths, each path is a list of entity names
        """
        # Get subgraphs from source and target
        source_graph = await self.get_knowledge_graph(source_entity, max_depth=max_depth)
        target_graph = await self.get_knowledge_graph(target_entity, max_depth=max_depth)

        # Build adjacency maps
        source_nodes = {n["entity_name"] for n in source_graph.nodes}
        target_nodes = {n["entity_name"] for n in target_graph.nodes}

        # Find intersection
        common_nodes = source_nodes & target_nodes

        paths = []
        if target_entity in source_nodes:
            paths.append([source_entity, target_entity])
        elif common_nodes:
            for intermediate in common_nodes:
                paths.append([source_entity, intermediate, target_entity])

        return paths

    def __await__(self) -> AsyncIterator[None]:
        """Support async context manager usage."""
        async def _init():
            await self.initialize()
            return self

        return _init().__await__()

    async def __aenter__(self) -> "LightRAGClient":
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.finalize()
