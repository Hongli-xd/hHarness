"""LightRAG integration for Historical Research Agent.

Provides async wrapper for LightRAG operations and credibility annotation.
"""

from .client import LightRAGClient
from .config import (
    create_embedding_func,
    create_lightrag_from_config,
    create_llm_client,
    index_document,
    load_config,
)
from .credibility import (
    CredibilityAnnotator,
    annotate_with_credibility,
    create_citation,
    get_annotator,
)
from .types import (
    AnnotatedClaim,
    Citation,
    EntityInfo,
    KnowledgeGraphResult,
    RelationInfo,
    SourceCredibility,
)

__all__ = [
    "LightRAGClient",
    "load_config",
    "create_llm_client",
    "create_embedding_func",
    "create_lightrag_from_config",
    "index_document",
    "CredibilityAnnotator",
    "annotate_with_credibility",
    "create_citation",
    "get_annotator",
    "AnnotatedClaim",
    "Citation",
    "EntityInfo",
    "KnowledgeGraphResult",
    "RelationInfo",
    "SourceCredibility",
]
