import os
import asyncio
import logging
import logging.config
from functools import partial
from lightrag import LightRAG, QueryParam
from lightrag.llm.anthropic import anthropic_complete
from lightrag.llm.ollama import ollama_embed
from lightrag.utils import EmbeddingFunc, logger, set_verbose_debug

WORKING_DIR = "./dickens"


def configure_logging(log_dir: str = "./logs", level: str = "INFO", verbose_debug: bool = False):
    """Configure logging for the application"""

    for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error", "lightrag"]:
        logger_instance = logging.getLogger(logger_name)
        logger_instance.handlers = []
        logger_instance.filters = []

    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.abspath(os.path.join(log_dir, "lightrag_anthropic_demo.log"))

    print(f"\nLightRAG Anthropic demo log file: {log_file_path}\n")

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {"format": "%(levelname)s: %(message)s"},
                "detailed": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stderr",
                },
                "file": {
                    "formatter": "detailed",
                    "class": "logging.handlers.RotatingFileHandler",
                    "filename": log_file_path,
                    "maxBytes": 10485760,
                    "backupCount": 5,
                    "encoding": "utf-8",
                },
            },
            "loggers": {
                "lightrag": {
                    "handlers": ["console", "file"],
                    "level": level,
                    "propagate": False,
                },
            },
        }
    )

    logger.setLevel(logging.INFO)
    set_verbose_debug(verbose_debug)


async def initialize_rag(config: dict):
    """Initialize LightRAG from YAML config"""
    llm_config = config.get("llm", {})
    embedding_config = config.get("embedding", {})
    storage_config = config.get("storage", {})
    query_config = config.get("query", {})
    chunking_config = config.get("chunking", {})
    cache_config = config.get("cache", {})
    neo4j_config = config.get("neo4j", {})

    # Set Neo4j environment variables
    if neo4j_config:
        if neo4j_config.get("uri"):
            os.environ["NEO4J_URI"] = neo4j_config["uri"]
        if neo4j_config.get("username"):
            os.environ["NEO4J_USERNAME"] = neo4j_config["username"]
        if neo4j_config.get("password"):
            os.environ["NEO4J_PASSWORD"] = neo4j_config["password"]

    # Build LLM kwargs
    llm_kwargs = {
        "max_tokens": llm_config.get("max_tokens", 8192),
        "timeout": llm_config.get("timeout", 600),
    }
    if llm_config.get("base_url"):
        llm_kwargs["base_url"] = llm_config["base_url"]

    # Embedding function (Ollama nomic)
    embedding_func = EmbeddingFunc(
        embedding_dim=embedding_config.get("dimension", 768),
        max_token_size=embedding_config.get("max_token_size", 8192),
        func=partial(
            ollama_embed.func,
            embed_model=embedding_config.get("model", "nomic-embed-text"),
            host=embedding_config.get("host", "http://localhost:11434"),
        ),
    )

    rag = LightRAG(
        working_dir=config.get("working_dir", WORKING_DIR),
        llm_model_func=anthropic_complete,
        llm_model_name=llm_config.get("model_name", "claude-sonnet-4-20250514"),
        embedding_func=embedding_func,
        llm_model_kwargs=llm_kwargs,
        llm_model_max_async=llm_config.get("max_async", 2),
        default_llm_timeout=llm_config.get("timeout", 600),
        # Storage
        kv_storage=storage_config.get("kv_storage", "JsonKVStorage"),
        vector_storage=storage_config.get("vector_storage", "NanoVectorDBStorage"),
        graph_storage=storage_config.get("graph_storage", "Neo4JStorage"),
        doc_status_storage=storage_config.get("doc_status_storage", "JsonDocStatusStorage"),
        # Query
        top_k=query_config.get("top_k", 60),
        chunk_top_k=query_config.get("chunk_top_k", 20),
        max_entity_tokens=query_config.get("max_entity_tokens", 6000),
        max_relation_tokens=query_config.get("max_relation_tokens", 8000),
        max_total_tokens=query_config.get("max_total_tokens", 30000),
        # Chunking
        chunk_token_size=chunking_config.get("chunk_token_size", 1200),
        chunk_overlap_token_size=chunking_config.get("chunk_overlap_token_size", 100),
        # Cache
        enable_llm_cache=cache_config.get("enable_llm_cache", True),
        enable_llm_cache_for_entity_extract=cache_config.get("enable_llm_cache_for_entity_extract", True),
    )

    await rag.initialize_storages()

    return rag


async def main():
    import yaml

    # Load config
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Configure logging
    log_config = config.get("logging", {})
    configure_logging(
        log_dir=log_config.get("log_dir", "./logs"),
        level=log_config.get("level", "INFO"),
        verbose_debug=log_config.get("verbose_debug", False),
    )

    # Check API key
    llm_config = config.get("llm", {})
    if not os.getenv("ANTHROPIC_API_KEY") and not llm_config.get("api_key"):
        print(
            "Error: ANTHROPIC_API_KEY environment variable is not set. "
            "Please set this variable before running the program."
        )
        return

    try:
        working_dir = config.get("working_dir", WORKING_DIR)
        if not os.path.exists(working_dir):
            os.mkdir(working_dir)

        # Clear old data files
        files_to_delete = [
            "graph_chunk_entity_relation.graphml",
            "kv_store_doc_status.json",
            "kv_store_full_docs.json",
            "kv_store_text_chunks.json",
            "vdb_chunks.json",
            "vdb_entities.json",
            "vdb_relationships.json",
        ]

        for file in files_to_delete:
            file_path = os.path.join(working_dir, file)
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Deleting old file:: {file_path}")

        rag = await initialize_rag(config)

        # Test embedding
        test_text = ["This is a test string for embedding."]
        embedding = await rag.embedding_func(test_text)
        embedding_dim = embedding.shape[1]
        print("\n=======================")
        print("Test embedding function")
        print("========================")
        print(f"Test dict: {test_text}")
        print(f"Detected embedding dimension: {embedding_dim}\n\n")

        # Insert documents
        input_file = config.get("input_file", os.path.join(os.path.dirname(__file__), "..", "input", "元和郡县图志.txt"))
        with open(input_file, "r", encoding="utf-8") as f:
            await rag.ainsert(f.read())

        # Query modes
        query_config = config.get("query", {})
        query_text = query_config.get("question", "这本书的主要内容是什么？")

        for mode in ["naive", "local", "global", "hybrid"]:
            print(f"\n=====================")
            print(f"Query mode: {mode}")
            print("=====================")
            print(
                await rag.aquery(
                    query_text,
                    param=QueryParam(
                        mode=mode,
                        enable_rerank=query_config.get("enable_rerank", False),
                    )
                )
            )

    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if rag:
            await rag.finalize_storages()


if __name__ == "__main__":
    asyncio.run(main())
    print("\nDone!")
