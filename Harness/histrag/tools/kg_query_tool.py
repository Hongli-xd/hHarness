"""Knowledge Graph Query Tool - the primary research tool for historians.

This tool provides the main interface to the LightRAG knowledge graph,
with three operations: entity query, fuzzy search, and relation path finding.
It is designed to be the agent's "primary eyes" for historical research.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field

from ..agent import BaseTool, ToolExecutionContext, ToolResult

from ..lightrag import (
    CredibilityAnnotator,
    EntityInfo,
    KnowledgeGraphResult,
    LightRAGClient,
    SourceCredibility,
)


class KGOperation(str, Enum):
    """Operations supported by the KG Query Tool."""

    ENTITY_QUERY = "entity_query"  # Get all attributes of an entity
    FUZZY_SEARCH = "fuzzy_search"  # Find entities by description
    RELATION_PATH = "relation_path"  # Find paths between two entities


class KGQueryInput(BaseModel):
    """Input schema for the KG Query Tool."""

    operation: KGOperation = Field(
        description="""Operation to perform:
- entity_query: Get all attributes of a historical entity by name
- fuzzy_search: Find entities by partial name or description
- relation_path: Find how two entities are connected"""
    )
    entity_name: str | None = Field(
        default=None,
        description="Entity name (required for entity_query and relation_path operations)",
    )
    query: str | None = Field(
        default=None,
        description="Search query (required for fuzzy_search operation)",
    )
    target_entity: str | None = Field(
        default=None,
        description="Target entity name for relation_path operation",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results for fuzzy_search",
    )
    max_depth: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum traversal depth for relation_path",
    )
    include_vector_data: bool = Field(
        default=False,
        description="Include vector similarity data in entity query results",
    )


class KGQueryTool(BaseTool):
    """Knowledge Graph Query Tool for historical research.

    This is the PRIMARY research tool for the historian agent.
    It provides three operations:

    1. entity_query: Given an entity name, returns all its attributes
       from the knowledge graph including type, description, sources,
       and connections to other entities.

    2. fuzzy_search: Given a partial name or description, finds all
       matching entities in the knowledge graph. Useful when the exact
       entity name is unknown.

    3. relation_path: Given two entity names, finds how they are
       connected through other entities. Uses BFS to find paths up
       to a specified depth.

    Results are annotated with credibility information when available.
    """

    name = "kg_query"
    description = """Query the historical knowledge graph for entities, relationships, and paths.

PRIMARY RESEARCH TOOL for historians. Use this before any other tool when researching historical facts.

Three operations:
1. entity_query: Get all attributes of an entity (e.g., "秦始皇", "史记")
2. fuzzy_search: Find entities by partial name or description
3. relation_path: Find how two entities are connected

Results include source credibility annotations (一手文献/二手研究/争议性说法).
"""
    input_model = KGQueryInput

    def __init__(
        self,
        rag_client: LightRAGClient,
        annotator: CredibilityAnnotator | None = None,
    ):
        """Initialize KG Query Tool.

        Args:
            rag_client: LightRAG client for graph queries
            annotator: Credibility annotator for source annotations
        """
        self.rag_client = rag_client
        self.annotator = annotator or CredibilityAnnotator()
        super().__init__()

    def is_read_only(self, arguments: KGQueryInput) -> bool:
        """KG queries are always read-only."""
        return True

    async def execute(
        self, arguments: KGQueryInput, context: ToolExecutionContext
    ) -> ToolResult:
        """Execute the KG query operation."""
        try:
            if arguments.operation == KGOperation.ENTITY_QUERY:
                return await self._entity_query(arguments)
            elif arguments.operation == KGOperation.FUZZY_SEARCH:
                return await self._fuzzy_search(arguments)
            elif arguments.operation == KGOperation.RELATION_PATH:
                return await self._relation_path(arguments)
            else:
                return ToolResult(
                    output=f"Unknown operation: {arguments.operation}",
                    is_error=True,
                )
        except Exception as e:
            return ToolResult(
                output=f"KG Query Error: {str(e)}",
                is_error=True,
            )

    async def _entity_query(self, args: KGQueryInput) -> ToolResult:
        """Query an entity by name."""
        if not args.entity_name:
            return ToolResult(
                output="entity_name is required for entity_query operation",
                is_error=True,
            )

        entity_info: EntityInfo = await self.rag_client.get_entity_info(
            args.entity_name, args.include_vector_data
        )

        # Get credibility annotations for this entity
        annotations = self.annotator.get_annotations_for_entity(args.entity_name)

        output = self._format_entity_info(entity_info, annotations)

        return ToolResult(output=output)

    async def _fuzzy_search(self, args: KGQueryInput) -> ToolResult:
        """Search for entities by partial name or description."""
        if not args.query:
            return ToolResult(
                output="query is required for fuzzy_search operation",
                is_error=True,
            )

        matches = await self.rag_client.search_labels(args.query, args.limit)

        if not matches:
            output = f"No entities found matching: {args.query}"
        else:
            lines = [f"Found {len(matches)} matching entities:\n"]
            for i, name in enumerate(matches, 1):
                # Get entity info for credibility
                annotations = self.annotator.get_annotations_for_entity(name)
                cred_str = self._format_credibility_tags(annotations)
                lines.append(f"{i}. {name} {cred_str}")

            output = "\n".join(lines)

        return ToolResult(output=output)

    async def _relation_path(self, args: KGQueryInput) -> ToolResult:
        """Find paths between two entities."""
        if not args.entity_name:
            return ToolResult(
                output="entity_name (source) is required for relation_path",
                is_error=True,
            )
        if not args.target_entity:
            return ToolResult(
                output="target_entity is required for relation_path",
                is_error=True,
            )

        paths = await self.rag_client.query_entity_paths(
            args.entity_name, args.target_entity, args.max_depth
        )

        if not paths:
            output = (
                f"No path found between '{args.entity_name}' and '{args.target_entity}' "
                f"within depth {args.max_depth}"
            )
        else:
            lines = [f"Found {len(paths)} path(s) between '{args.entity_name}' and '{args.target_entity}':\n"]
            for i, path in enumerate(paths, 1):
                path_str = " → ".join(path)
                lines.append(f"  {i}. {path_str}")

            output = "\n".join(lines)

        return ToolResult(output=output)

    def _format_entity_info(
        self, entity: EntityInfo, annotations: list
    ) -> str:
        """Format entity information with credibility annotations."""
        lines = [f"# {entity.entity_name}"]

        if entity.entity_type:
            lines.append(f"**类型**: {entity.entity_type}")

        if entity.description:
            lines.append(f"\n**描述**: {entity.description}")

        # Credibility annotations
        if annotations:
            lines.append("\n**来源可信度**:")
            for ann in annotations:
                cred_emoji = self._credibility_emoji(ann.credibility)
                lines.append(f"  {cred_emoji} [{ann.credibility}] {ann.claim_text}")
                if ann.notes:
                    lines.append(f"      备注: {ann.notes}")
        else:
            lines.append("\n**来源可信度**: 未标注")

        # Metadata
        if entity.source_id:
            lines.append(f"\n**来源ID**: {entity.source_id}")
        if entity.file_path:
            lines.append(f"**文件**: {entity.file_path}")
        if entity.created_at:
            lines.append(f"**创建时间**: {entity.created_at}")

        return "\n".join(lines)

    def _format_credibility_tags(self, annotations: list) -> str:
        """Format credibility tags for entity list display."""
        if not annotations:
            return ""

        cred_set = set(ann.credibility for ann in annotations)
        tags = [f"[{c}]" for c in cred_set]
        return " ".join(tags)

    def _credibility_emoji(self, credibility: str) -> str:
        """Return emoji for credibility level."""
        emoji_map = {
            "一手文献": "📜",
            "二手研究": "📚",
            "争议性说法": "⚠️",
            "未知": "❓",
        }
        return emoji_map.get(credibility, "📄")
