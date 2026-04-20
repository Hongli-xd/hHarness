"""Data types for LightRAG integration."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SourceCredibility(Enum):
    """Historical source credibility classification."""

    PRIMARY = "一手文献"  # Primary source - contemporary to events
    SECONDARY = "二手研究"  # Secondary source - analysis of primary sources
    DISPUTED = "争议性说法"  # Disputed claim - multiple interpretations exist
    UNKNOWN = "未知"  # Unknown credibility


@dataclass
class EntityInfo:
    """Information about a historical entity from the knowledge graph."""

    entity_name: str
    entity_type: str | None = None
    description: str | None = None
    source_id: str | None = None
    file_path: str | None = None
    created_at: str | None = None
    vector_data: dict[str, Any] | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EntityInfo":
        """Create EntityInfo from LightRAG get_entity_info response."""
        graph_data = data.get("graph_data", {})
        return cls(
            entity_name=data.get("entity_name", ""),
            entity_type=graph_data.get("entity_type"),
            description=graph_data.get("description"),
            source_id=graph_data.get("source_id"),
            file_path=graph_data.get("file_path"),
            created_at=graph_data.get("created_at"),
            vector_data=data.get("vector_data"),
            raw_data=data,
        )


@dataclass
class RelationInfo:
    """Information about a relationship between entities."""

    source_entity: str
    target_entity: str
    description: str | None = None
    keywords: list[str] = field(default_factory=list)
    weight: float = 1.0
    source_id: str | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, src: str, tgt: str, data: dict[str, Any]) -> "RelationInfo":
        """Create RelationInfo from LightRAG response."""
        return cls(
            source_entity=src,
            target_entity=tgt,
            description=data.get("description"),
            keywords=data.get("keywords", []),
            weight=data.get("weight", 1.0),
            source_id=data.get("source_id"),
            raw_data=data,
        )


@dataclass
class KnowledgeGraphResult:
    """Result from knowledge graph traversal."""

    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    is_truncated: bool = False


@dataclass
class AnnotatedClaim:
    """A historical claim with source credibility annotation."""

    claim: str
    credibility: SourceCredibility
    source_entities: list[str] = field(default_factory=list)
    source_type: str | None = None  # e.g., "史书", "考古", "研究论文"
    period: str | None = None  # e.g., "西汉", "唐代"
    notes: str | None = None
    kg_node_ids: list[str] = field(default_factory=list)


@dataclass
class Citation:
    """A citation linking a claim to its source."""

    claim: str
    kg_node_ids: list[str]
    credibility: SourceCredibility
    citation_text: str | None = None

    def format(self, style: str = "inline") -> str:
        """Format citation for output."""
        if style == "inline":
            node_refs = ", ".join(f"[{n}]" for n in self.kg_node_ids)
            cred_tag = f"[{self.credibility.value}]"
            return f"{cred_tag} {self.claim} {node_refs}"
        elif style == "footnote":
            return f"{self.claim} ({self.credibility.value}: {', '.join(self.kg_node_ids)})"
        else:
            return str(self)
