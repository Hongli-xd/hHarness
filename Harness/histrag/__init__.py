"""HistRAG - Historical Research Agent (standalone, no OpenHarness dependency)."""

__version__ = "0.1.0"
__author__ = "HistRAG Team"

from . import coordinator, integration, lightrag, prompts, tools, agent, api
from .coordinator.historian import HistorianCoordinator, KGVerifierAgent
from .integration import HistorianRuntime, create_historical_runtime, run_historical_query
from .lightrag import (
    CredibilityAnnotator,
    LightRAGClient,
    SourceCredibility,
    annotate_with_credibility,
    create_citation,
    get_annotator,
)
from .prompts.historian import build_historian_system_prompt, build_research_context_prompt

__all__ = [
    # Core
    "__version__",
    # Submodules
    "agent",
    "api",
    "coordinator",
    "integration",
    "lightrag",
    "prompts",
    "tools",
    # Integration
    "HistorianRuntime",
    "create_historical_runtime",
    "run_historical_query",
    # LightRAG
    "LightRAGClient",
    "CredibilityAnnotator",
    "SourceCredibility",
    "annotate_with_credibility",
    "create_citation",
    "get_annotator",
    # Prompts
    "build_historian_system_prompt",
    "build_research_context_prompt",
    # Coordinator
    "HistorianCoordinator",
    "KGVerifierAgent",
]