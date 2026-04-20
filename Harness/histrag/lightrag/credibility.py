"""Independent credibility annotation layer for historical sources.

This module provides a separate annotation system for tracking source credibility
that works alongside (not embedded in) the LightRAG knowledge graph.

Annotations are stored in: ~/.openharness/histrag/annotations.json
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .types import AnnotatedClaim, Citation, SourceCredibility


# Default annotation storage path
DEFAULT_ANNOTATION_DIR = Path.home() / ".openharness" / "histrag"
DEFAULT_ANNOTATION_FILE = DEFAULT_ANNOTATION_DIR / "annotations.json"


@dataclass
class CredibilityAnnotation:
    """A credibility annotation for a historical claim."""

    claim_id: str
    claim_text: str
    credibility: str  # SourceCredibility.value
    source_entities: list[str] = field(default_factory=list)
    source_type: str | None = None  # e.g., "史书", "考古", "研究论文"
    period: str | None = None  # e.g., "西汉", "唐代"
    notes: str | None = None
    annotated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    kg_node_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)  # e.g., ["争议性", "待考证"]


class CredibilityAnnotator:
    """Manages credibility annotations for historical claims.

    Provides functions to annotate, store, and retrieve source credibility
    information independently from the LightRAG knowledge graph.
    """

    def __init__(self, annotation_file: Path | str = DEFAULT_ANNOTATION_FILE):
        """Initialize annotator.

        Args:
            annotation_file: Path to JSON file for storing annotations
        """
        self.annotation_file = Path(annotation_file)
        self.annotation_file.parent.mkdir(parents=True, exist_ok=True)
        self._annotations: dict[str, CredibilityAnnotation] = {}
        self._load()

    def _load(self) -> None:
        """Load annotations from file."""
        if self.annotation_file.exists():
            try:
                with open(self.annotation_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._annotations = {
                        k: CredibilityAnnotation(**v) for k, v in data.items()
                    }
            except (json.JSONDecodeError, TypeError):
                self._annotations = {}

    def _save(self) -> None:
        """Save annotations to file."""
        data = {k: asdict(v) for k, v in self._annotations.items()}
        with open(self.annotation_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def annotate(
        self,
        claim_text: str,
        credibility: SourceCredibility,
        source_entities: list[str] | None = None,
        source_type: str | None = None,
        period: str | None = None,
        notes: str | None = None,
        kg_node_ids: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> AnnotatedClaim:
        """Annotate a historical claim with credibility information.

        Args:
            claim_text: The historical claim being annotated
            credibility: Source credibility level
            source_entities: List of source entities supporting this claim
            source_type: Type of source (史书/考古/研究论文等)
            period: Historical period (西汉/唐代等)
            notes: Additional notes about this claim
            kg_node_ids: LightRAG node IDs for sources
            tags: Additional tags (争议性/待考证等)

        Returns:
            AnnotatedClaim object
        """
        claim_id = str(uuid.uuid4())[:8]

        annotation = CredibilityAnnotation(
            claim_id=claim_id,
            claim_text=claim_text,
            credibility=credibility.value,
            source_entities=source_entities or [],
            source_type=source_type,
            period=period,
            notes=notes,
            kg_node_ids=kg_node_ids or [],
            tags=tags or [],
        )

        self._annotations[claim_id] = annotation
        self._save()

        return AnnotatedClaim(
            claim=claim_text,
            credibility=credibility,
            source_entities=source_entities or [],
            source_type=source_type,
            period=period,
            notes=notes,
            kg_node_ids=kg_node_ids or [],
        )

    def get_annotation(self, claim_id: str) -> CredibilityAnnotation | None:
        """Retrieve an annotation by ID."""
        return self._annotations.get(claim_id)

    def get_annotations_for_entity(self, entity_name: str) -> list[CredibilityAnnotation]:
        """Get all annotations that reference an entity."""
        return [
            ann
            for ann in self._annotations.values()
            if entity_name in ann.source_entities
        ]

    def get_annotations_by_credibility(
        self, credibility: SourceCredibility
    ) -> list[CredibilityAnnotation]:
        """Get all annotations with a specific credibility level."""
        return [
            ann
            for ann in self._annotations.values()
            if ann.credibility == credibility.value
        ]

    def update_annotation(
        self, claim_id: str, updates: dict[str, Any]
    ) -> CredibilityAnnotation | None:
        """Update an existing annotation.

        Args:
            claim_id: ID of annotation to update
            updates: Dict of fields to update

        Returns:
            Updated annotation or None if not found
        """
        if claim_id not in self._annotations:
            return None

        annotation = self._annotations[claim_id]
        for key, value in updates.items():
            if hasattr(annotation, key):
                setattr(annotation, key, value)

        self._save()
        return annotation

    def delete_annotation(self, claim_id: str) -> bool:
        """Delete an annotation.

        Returns:
            True if deleted, False if not found
        """
        if claim_id in self._annotations:
            del self._annotations[claim_id]
            self._save()
            return True
        return False

    def list_annotations(
        self,
        credibility: SourceCredibility | None = None,
        limit: int = 100,
    ) -> list[CredibilityAnnotation]:
        """List annotations with optional filtering.

        Args:
            credibility: Filter by credibility level
            limit: Maximum number to return

        Returns:
            List of annotations
        """
        annotations = list(self._annotations.values())

        if credibility:
            annotations = [a for a in annotations if a.credibility == credibility.value]

        # Sort by annotated_at descending (most recent first)
        annotations.sort(key=lambda a: a.annotated_at, reverse=True)

        return annotations[:limit]


# Global annotator instance
_default_annotator: CredibilityAnnotator | None = None


def get_annotator() -> CredibilityAnnotator:
    """Get the default global annotator instance."""
    global _default_annotator
    if _default_annotator is None:
        _default_annotator = CredibilityAnnotator()
    return _default_annotator


def annotate_with_credibility(
    claim: str,
    kg_results: dict[str, Any] | None = None,
    credibility: SourceCredibility = SourceCredibility.UNKNOWN,
    **kwargs: Any,
) -> AnnotatedClaim:
    """Convenience function to annotate a claim with credibility.

    Args:
        claim: The historical claim to annotate
        kg_results: Results from LightRAG query (used to extract source entities)
        credibility: Credibility level
        **kwargs: Additional arguments passed to annotator.annotate()

    Returns:
        AnnotatedClaim object
    """
    annotator = get_annotator()

    source_entities = kwargs.pop("source_entities", None)
    kg_node_ids = kwargs.pop("kg_node_ids", None)

    # Try to extract source entities from KG results
    if kg_results and source_entities is None:
        source_entities = []
        if "entities" in kg_results:
            source_entities = [e.get("entity_name", "") for e in kg_results["entities"]]
        elif "nodes" in kg_results:
            source_entities = [n.get("entity_name", "") for n in kg_results["nodes"]]

    if kg_results and kg_node_ids is None:
        kg_node_ids = kg_results.get("node_ids", [])

    return annotator.annotate(
        claim_text=claim,
        credibility=credibility,
        source_entities=source_entities,
        kg_node_ids=kg_node_ids,
        **kwargs,
    )


def create_citation(
    claim: str,
    kg_results: dict[str, Any] | None = None,
    credibility: SourceCredibility = SourceCredibility.UNKNOWN,
    **kwargs: Any,
) -> Citation:
    """Create a citation linking a claim to its sources.

    Args:
        claim: The claim being cited
        kg_results: LightRAG query results
        credibility: Credibility level
        **kwargs: Additional arguments

    Returns:
        Citation object
    """
    kg_node_ids = kg_results.get("node_ids", []) if kg_results else []
    if not kg_node_ids and kg_results:
        if "entities" in kg_results:
            kg_node_ids = [e.get("id", "") for e in kg_results["entities"]]
        elif "nodes" in kg_results:
            kg_node_ids = [n.get("id", "") for n in kg_results["nodes"]]

    return Citation(
        claim=claim,
        kg_node_ids=kg_node_ids,
        credibility=credibility,
    )
