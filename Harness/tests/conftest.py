"""Pytest configuration and fixtures."""

import sys
from pathlib import Path

# Add harness to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


@pytest.fixture
def mock_rag_client():
    """Create a mock LightRAG client."""
    from tests import create_mock_rag_client
    return create_mock_rag_client()


@pytest.fixture
def mock_annotator():
    """Create a mock credibility annotator."""
    from tests import create_mock_annotator
    return create_mock_annotator()


@pytest.fixture
def mock_entity_info():
    """Create mock entity info."""
    from tests import MockEntityInfo
    return MockEntityInfo(
        entity_name="秦始皇",
        entity_type="人物",
        description="秦朝开国皇帝",
        source_id="test-source-1",
    )


@pytest.fixture
def mock_kg_result():
    """Create mock knowledge graph result."""
    from tests import MockKnowledgeGraphResult
    return MockKnowledgeGraphResult(
        nodes=[
            {"entity_name": "秦始皇", "entity_type": "人物"},
            {"entity_name": "秦朝", "entity_type": "朝代"},
        ],
        edges=[
            {"source": "秦始皇", "target": "秦朝", "description": "建立"},
        ],
        is_truncated=False,
    )
