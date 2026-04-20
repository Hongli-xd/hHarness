"""Test fixtures - standalone version with no external dependencies."""

import sys
from pathlib import Path

# Add harness to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent))


class MockEntityInfo:
    """Mock EntityInfo for tests."""

    def __init__(self, entity_name, entity_type=None, description=None, source_id=None):
        self.entity_name = entity_name
        self.entity_type = entity_type
        self.description = description
        self.source_id = source_id


class MockKnowledgeGraphResult:
    """Mock KnowledgeGraphResult for tests."""

    def __init__(self, nodes, edges, is_truncated=False):
        self.nodes = nodes
        self.edges = edges
        self.is_truncated = is_truncated


class MockCredibilityAnnotation:
    """Mock CredibilityAnnotation for tests."""

    def __init__(self, claim_text, credibility, source_entities=None):
        self.claim_text = claim_text
        self.credibility = credibility
        self.source_entities = source_entities or []


def create_mock_rag_client():
    """Create a mock LightRAG client with all methods."""
    from unittest.mock import MagicMock, AsyncMock

    client = MagicMock()

    # Mock entity info
    entity_info = MockEntityInfo(
        entity_name="秦始皇",
        entity_type="人物",
        description="秦朝开国皇帝",
        source_id="test-source-1",
    )
    client.get_entity_info = AsyncMock(return_value=entity_info)

    # Mock search labels
    client.search_labels = AsyncMock(return_value=["秦始皇", "秦朝", "兵马俑"])

    # Mock knowledge graph
    kg_result = MockKnowledgeGraphResult(
        nodes=[
            {"entity_name": "秦始皇", "entity_type": "人物"},
            {"entity_name": "秦朝", "entity_type": "朝代"},
        ],
        edges=[
            {"source": "秦始皇", "target": "秦朝", "description": "建立"},
        ],
        is_truncated=False,
    )
    client.get_knowledge_graph = AsyncMock(return_value=kg_result)

    # Mock aquery
    client.aquery = AsyncMock(
        return_value='秦始皇（公元前259年—公元前210年），是中国历史上第一个使用"皇帝"称号的君主...'
    )

    # Mock aquery_data
    client.aquery_data = AsyncMock(
        return_value={
            "entities": [{"entity_name": "秦始皇", "description": "秦朝开国皇帝"}],
            "relations": [{"source": "秦始皇", "target": "秦朝", "description": "建立"}],
            "chunks": [{"chunk_text": "秦始皇统一六国..."}],
        }
    )

    # Mock insert
    client.insert = AsyncMock()

    # Mock query_entity_paths
    client.query_entity_paths = AsyncMock(
        return_value=[["秦始皇", "秦朝"], ["秦始皇", "统一", "六国"]]
    )

    return client


def create_mock_annotator():
    """Create a mock credibility annotator."""
    from unittest.mock import MagicMock

    annotator = MagicMock()

    annotation = MockCredibilityAnnotation(
        claim_text="史记记载秦始皇统一六国",
        credibility="一手文献",
        source_entities=["史记", "资治通鉴"],
    )

    annotator.get_annotation = MagicMock(return_value=annotation)
    annotator.get_annotations_for_entity = MagicMock(return_value=[annotation])
    annotator.list_annotations = MagicMock(return_value=[annotation])

    return annotator
