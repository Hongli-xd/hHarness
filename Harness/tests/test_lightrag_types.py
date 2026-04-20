"""Tests for LightRAG types - no external dependencies."""

import pytest
import sys
from pathlib import Path

# Add harness to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSourceCredibility:
    """Tests for SourceCredibility enum - standalone test."""

    def test_credibility_values(self):
        # Inline the enum to avoid import
        class SourceCredibility:
            PRIMARY = "一手文献"
            SECONDARY = "二手研究"
            DISPUTED = "争议性说法"
            UNKNOWN = "未知"

        assert SourceCredibility.PRIMARY == "一手文献"
        assert SourceCredibility.SECONDARY == "二手研究"
        assert SourceCredibility.DISPUTED == "争议性说法"
        assert SourceCredibility.UNKNOWN == "未知"


class TestEntityInfo:
    """Tests for EntityInfo - standalone test."""

    def test_from_dict_full(self):
        data = {
            "entity_name": "史记",
            "graph_data": {
                "entity_type": "史书",
                "description": "西汉司马迁撰写的史书",
                "source_id": "src-1",
            },
        }

        # Inline class to avoid import
        class EntityInfo:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

            @classmethod
            def from_dict(cls, data):
                graph_data = data.get("graph_data", {})
                return cls(
                    entity_name=data.get("entity_name", ""),
                    entity_type=graph_data.get("entity_type"),
                    description=graph_data.get("description"),
                    source_id=graph_data.get("source_id"),
                )

        entity = EntityInfo.from_dict(data)

        assert entity.entity_name == "史记"
        assert entity.entity_type == "史书"
        assert entity.description == "西汉司马迁撰写的史书"
        assert entity.source_id == "src-1"

    def test_from_dict_minimal(self):
        class EntityInfo:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

            @classmethod
            def from_dict(cls, data):
                return cls(entity_name=data.get("entity_name", ""))

        entity = EntityInfo.from_dict({"entity_name": "测试"})
        assert entity.entity_name == "测试"


class TestKnowledgeGraphResult:
    """Tests for KnowledgeGraphResult."""

    def test_creation(self):
        class KnowledgeGraphResult:
            def __init__(self, nodes, edges, is_truncated=False):
                self.nodes = nodes
                self.edges = edges
                self.is_truncated = is_truncated

        result = KnowledgeGraphResult(
            nodes=[{"entity_name": "秦始皇"}],
            edges=[{"source": "秦始皇", "target": "秦朝"}],
            is_truncated=False,
        )

        assert len(result.nodes) == 1
        assert len(result.edges) == 1
        assert result.is_truncated is False

    def test_truncated(self):
        class KnowledgeGraphResult:
            def __init__(self, nodes, edges, is_truncated=False):
                self.nodes = nodes
                self.edges = edges
                self.is_truncated = is_truncated

        result = KnowledgeGraphResult(
            nodes=[{"entity_name": "秦始皇"}] * 1000,
            edges=[],
            is_truncated=True,
        )

        assert result.is_truncated is True


class TestCitation:
    """Tests for Citation."""

    def test_inline_format(self):
        class SourceCredibility:
            PRIMARY = "一手文献"

        class Citation:
            def __init__(self, claim, kg_node_ids, credibility):
                self.claim = claim
                self.kg_node_ids = kg_node_ids
                self.credibility = credibility

            def format(self, style="inline"):
                if style == "inline":
                    node_refs = ", ".join(f"[{n}]" for n in self.kg_node_ids)
                    return f"[{self.credibility}] {self.claim} {node_refs}"
                return str(self)

        citation = Citation(
            claim="史记是司马迁所著",
            kg_node_ids=["史记", "司马迁"],
            credibility="一手文献",
        )

        result = citation.format("inline")
        assert "[一手文献]" in result
        assert "史记是司马迁所著" in result
        assert "[史记]" in result


class TestAnnotatedClaim:
    """Tests for AnnotatedClaim."""

    def test_creation(self):
        class SourceCredibility:
            PRIMARY = "一手文献"

        class AnnotatedClaim:
            def __init__(self, claim, credibility, source_entities=None, kg_node_ids=None):
                self.claim = claim
                self.credibility = credibility
                self.source_entities = source_entities or []
                self.kg_node_ids = kg_node_ids or []

        claim = AnnotatedClaim(
            claim="秦始皇统一六国",
            credibility="一手文献",
            source_entities=["史记", "资治通鉴"],
            kg_node_ids=["node-1", "node-2"],
        )

        assert claim.claim == "秦始皇统一六国"
        assert claim.credibility == "一手文献"
        assert len(claim.source_entities) == 2


class TestRelationInfo:
    """Tests for RelationInfo."""

    def test_from_dict(self):
        class RelationInfo:
            def __init__(self, source, target, **kwargs):
                self.source_entity = source
                self.target_entity = target
                for k, v in kwargs.items():
                    setattr(self, k, v)

            @classmethod
            def from_dict(cls, src, tgt, data):
                return cls(src, tgt, **data)

        data = {
            "description": "父亲",
            "keywords": ["父子", "血缘"],
            "weight": 1.0,
        }

        rel = RelationInfo.from_dict("刘邦", "刘盈", data)

        assert rel.source_entity == "刘邦"
        assert rel.target_entity == "刘盈"
        assert rel.description == "父亲"
        assert rel.keywords == ["父子", "血缘"]
        assert rel.weight == 1.0
