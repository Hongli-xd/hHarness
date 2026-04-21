"""LightRAG configuration loader from YAML config.

This module provides functions to create a LightRAG client from a config.yaml file,
similar to the demo in /home/selom/projects/literag/LightRAG/examples/lightrag_anthropic_demo.py.
"""

from __future__ import annotations

import os
from functools import partial
from pathlib import Path
from typing import Any

import yaml

from lightrag import LightRAG


def load_config(config_path: str | Path) -> dict[str, Any]:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config.yaml

    Returns:
        Configuration dictionary
    """
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def create_llm_client(
    config: dict[str, Any],
) -> tuple[Any, dict[str, Any]]:
    """Create LLM client from config.

    Args:
        config: Configuration dict with 'llm' section

    Returns:
        Tuple of (llm_func, llm_kwargs)
    """
    from lightrag.llm.anthropic import anthropic_complete

    llm_config = config.get("llm", {})
    model_func = llm_config.get("model_func", "anthropic")

    api_key = os.environ.get("ANTHROPIC_API_KEY") or llm_config.get("api_key")
    if not api_key:
        api_key = os.environ.get("MINIMAX_API_KEY")

    base_url = llm_config.get("base_url")
    model_name = llm_config.get("model_name", "claude-sonnet-4-20250514")

    llm_kwargs = {
        "api_key": api_key,
        "max_tokens": llm_config.get("max_tokens", 8192),
        "timeout": llm_config.get("timeout", 600),
    }
    if base_url:
        llm_kwargs["base_url"] = base_url

    if model_func == "anthropic":
        return anthropic_complete, llm_kwargs, model_name

    raise ValueError(f"Unknown model_func: {model_func}")


def create_embedding_func(config: dict[str, Any]):
    """Create embedding function from config.

    Supports two modes:
    - Ollama (default): uses ollama_embed with local Ollama server
    - API mode: uses openai-compatible embedding API when api_key is present

    Args:
        config: Configuration dict with 'embedding' section

    Returns:
        EmbeddingFunc instance
    """
    from lightrag.utils import EmbeddingFunc

    embedding_config = config.get("embedding", {})
    api_key = embedding_config.get("api_key")
    base_url = embedding_config.get("base_url")

    if api_key and base_url:
        # Use OpenAI-compatible API embedding
        from lightrag.llm.openai import openai_embed

        return EmbeddingFunc(
            embedding_dim=embedding_config.get("dimension", 768),
            max_token_size=embedding_config.get("max_token_size", 8192),
            func=partial(
                openai_embed.func,  # Use .func to avoid double-wrapping from decorator
                api_key=api_key,
                model=embedding_config.get("model", "text-embedding-3-small"),
                base_url=base_url,
            ),
        )
    else:
        # Fallback to Ollama
        from lightrag.llm.ollama import ollama_embed

        return EmbeddingFunc(
            embedding_dim=embedding_config.get("dimension", 768),
            max_token_size=embedding_config.get("max_token_size", 8192),
            func=partial(
                ollama_embed.func,
                embed_model=embedding_config.get("model", "nomic-embed-text"),
                host=embedding_config.get("host", "http://localhost:11434"),
            ),
        )


def create_lightrag_from_config(
    config_path: str | Path,
    **overrides: Any,
) -> tuple[Any, dict[str, Any]]:
    """Create LightRAG instance from config.yaml.

    Args:
        config_path: Path to config.yaml
        **overrides: Override config values

    Returns:
        Tuple of (LightRAG instance, config dict)

    Example:
        rag, config = create_lightrag_from_config("/path/to/config.yaml")
        await rag.initialize()
        result = await rag.aquery("问题")
    """
    config = load_config(config_path)

    # Apply overrides
    for key, value in overrides.items():
        if "." in key:
            # Nested key like "llm.model_name"
            parts = key.split(".")
            d = config
            for part in parts[:-1]:
                d = d.setdefault(part, {})
            d[parts[-1]] = value
        else:
            config[key] = value

    # Neo4j config
    neo4j_config = config.get("neo4j", {})
    if neo4j_config.get("uri"):
        os.environ["NEO4J_URI"] = neo4j_config["uri"]
    if neo4j_config.get("username"):
        os.environ["NEO4J_USERNAME"] = neo4j_config["username"]
    if neo4j_config.get("password"):
        os.environ["NEO4J_PASSWORD"] = neo4j_config["password"]

    # Create LLM client
    llm_func, llm_kwargs, model_name = create_llm_client(config)

    # Create embedding function
    embedding_func = create_embedding_func(config)

    # Build LightRAG
    rag = LightRAG(
        working_dir=os.path.expanduser(config.get("working_dir", "./rag_storage")),
        llm_model_func=llm_func,
        llm_model_name=model_name,
        embedding_func=embedding_func,
        llm_model_kwargs=llm_kwargs,
        llm_model_max_async=config.get("llm", {}).get("max_async", 2),
        default_llm_timeout=config.get("llm", {}).get("timeout", 600),
        # Embedding
        embedding_batch_num=config.get("embedding", {}).get("batch_size", 5),
        # Storage
        kv_storage=config.get("storage", {}).get("kv_storage", "JsonKVStorage"),
        vector_storage=config.get("storage", {}).get("vector_storage", "NanoVectorDBStorage"),
        graph_storage=config.get("storage", {}).get("graph_storage", "Neo4JStorage"),
        doc_status_storage=config.get("storage", {}).get("doc_status_storage", "JsonDocStatusStorage"),
        # Query
        top_k=config.get("query", {}).get("top_k", 60),
        chunk_top_k=config.get("query", {}).get("chunk_top_k", 20),
        max_entity_tokens=config.get("query", {}).get("max_entity_tokens", 6000),
        max_relation_tokens=config.get("query", {}).get("max_relation_tokens", 8000),
        max_total_tokens=config.get("query", {}).get("max_total_tokens", 30000),
        # Chunking
        chunk_token_size=config.get("chunking", {}).get("chunk_token_size", 1200),
        chunk_overlap_token_size=config.get("chunking", {}).get("chunk_overlap_token_size", 100),
        # Cache
        enable_llm_cache=config.get("cache", {}).get("enable_llm_cache", True),
        enable_llm_cache_for_entity_extract=config.get("cache", {}).get("enable_llm_cache_for_entity_extract", True),
        # Entity/Relation merge
        force_llm_summary_on_merge=config.get("merge", {}).get("force_llm_summary_on_merge", 17),
    )

    return rag, config


def index_document(
    rag: Any,
    input_file: str | Path,
) -> None:
    """Index a document into LightRAG.

    Args:
        rag: LightRAG instance (initialized)
        input_file: Path to document to index
    """
    with open(input_file, "r", encoding="utf-8") as f:
        import asyncio
        asyncio.run(rag.ainsert(f.read()))


__all__ = [
    "load_config",
    "create_llm_client",
    "create_embedding_func",
    "create_lightrag_from_config",
    "index_document",
]
