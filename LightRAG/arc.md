# LightRAG 架构分析

## 1. 系统概述

LightRAG 是一个基于知识图谱的检索增强生成（RAG）框架，通过从文档中提取实体和关系构建知识图谱，并结合多模态检索（local、global、hybrid、mix、naive）实现高效问答。

## 2. 核心架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         LightRAG                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Document    │  │   Query      │  │   Knowledge Graph    │  │
│  │  Ingestion  │──▶│   Processing │──▶│   & Retrieval       │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  KV Storage   │    │ Vector Storage│    │ Graph Storage │
│  (缓存/文档)   │    │  (向量检索)   │    │ (知识图谱)    │
└───────────────┘    └───────────────┘    └───────────────┘
```

## 3. 数据流架构

### 3.1 索引流程 (Indexing Pipeline)

```
Document Input
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│  1. Chunking (chunking_by_token_size)                       │
│     - 按 token 大小分块                                     │
│     - 默认 chunk_token_size=1200, overlap=100               │
└─────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Entity Extraction (extract_entities)                      │
│     - 调用 LLM 提取实体和关系                                 │
│     - 使用 PROMPTS["entity_extraction_system_prompt"]        │
│     - 支持多轮提取 (max_gleaning)                           │
└─────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Knowledge Graph Construction                             │
│     - entities_vdb: 实体向量存储                             │
│     - relationships_vdb: 关系向量存储                         │
│     - chunk_entity_relation_graph: 图存储                    │
│     - entity_chunks/relation_chunks: chunk 追踪             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 查询流程 (Query Pipeline)

```
User Query
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│  Keyword Extraction (keywords_extraction)                    │
│     - high_level_keywords: 高层概念                         │
│     - low_level_keywords: 具体实体                          │
└─────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│  Mode Selection: local/global/hybrid/naive/mix/bypass       │
└─────────────────────────────────────────────────────────────┘
      │
      ├──────▶ local ────▶ 基于实体的上下文检索
      │
      ├──────▶ global ───▶ 基于社区/关系的全局检索
      │
      ├──────▶ hybrid ───▶ local + global 组合
      │
      ├──────▶ mix ──────▶ KG + Vector 融合 (推荐)
      │
      └──────▶ naive ────▶ 纯向量检索
```

## 4. 存储层架构

### 4.1 四大存储类型

| 存储类型 | 用途 | 默认实现 |
|---------|------|---------|
| **KV Storage** | LLM 响应缓存、文本块、文档信息 | JsonKVStorage |
| **Vector Storage** | 实体/关系/文本块的向量嵌入 | NanoVectorDBStorage |
| **Graph Storage** | 实体-关系图结构 | NetworkXStorage |
| **Doc Status Storage** | 文档处理状态追踪 | JsonDocStatusStorage |

### 4.2 存储命名空间

```python
namespace NameSpace:
    KV_STORE_LLM_RESPONSE_CACHE = "kv_store_llm_response_cache"
    KV_STORE_TEXT_CHUNKS = "kv_store_text_chunks"
    KV_STORE_FULL_DOCS = "kv_store_full_docs"
    KV_STORE_FULL_ENTITIES = "kv_store_full_entities"
    KV_STORE_FULL_RELATIONS = "kv_store_full_relations"
    KV_STORE_ENTITY_CHUNKS = "kv_store_entity_chunks"
    KV_STORE_RELATION_CHUNKS = "kv_store_relation_chunks"

    VECTOR_STORE_ENTITIES = "vector_store_entities"
    VECTOR_STORE_RELATIONSHIPS = "vector_store_relationships"
    VECTOR_STORE_CHUNKS = "vector_store_chunks"

    GRAPH_STORE_CHUNK_ENTITY_RELATION = "graph_store_chunk_entity_relation"

    DOC_STATUS = "doc_status"
```

### 4.3 可插拔存储实现 (kg/)

```
kg/
├── json_kv_impl.py          # JSON 文件存储 (开发用)
├── json_doc_status_impl.py  # JSON 文档状态
├── nano_vector_db_impl.py   # 轻量级向量数据库
├── networkx_impl.py         # NetworkX 内存图
├── neo4j_impl.py           # Neo4j 图数据库
├── postgres_impl.py        # PostgreSQL (PGVector)
├── mongodb_impl.py         # MongoDB
├── redis_impl.py           # Redis
├── milvus_impl.py          # Milvus
├── qdrant_impl.py          # Qdrant
├── opensearch_impl.py      # OpenSearch
├── faiss_impl.py           # FAISS
└── memgraph_impl.py        # Memgraph
```

## 5. 核心组件

### 5.1 LightRAG 主类 (lightrag.py)

```python
@dataclass
class LightRAG:
    # 存储配置
    kv_storage: str           # KV 存储类型
    vector_storage: str      # 向量存储类型
    graph_storage: str       # 图存储类型
    doc_status_storage: str  # 文档状态存储

    # LLM 配置
    llm_model_func: Callable      # LLM 调用函数
    embedding_func: EmbeddingFunc # 嵌入函数

    # 检索参数
    top_k: int               # 实体/关系检索数量
    chunk_top_k: int        # 文本块检索数量
    max_total_tokens: int   # Token 预算上限

    # 关键方法
    async initialize_storages()   # 初始化所有存储
    async finalize_storages()      # 清理所有存储
    async ainsert(text)            # 插入文档
    async aquery(query, mode)      # 查询
```

**关键初始化流程**:
```python
rag = LightRAG(working_dir, llm_model_func, embedding_func)
await rag.initialize_storages()  # 必须调用
# ... 使用 ...
await rag.finalize_storages()    # 清理
```

### 5.2 Base Storage 抽象 (base.py)

```
BaseStorage (抽象基类)
├── BaseKVStorage
│   ├── get_by_id(id) / get_by_ids(ids)
│   ├── filter_keys(keys)
│   ├── upsert(data)
│   ├── delete(ids)
│   └── is_empty()
│
├── BaseVectorStorage
│   ├── query(query, top_k, query_embedding)
│   ├── upsert(data)
│   ├── delete_entity(name) / delete_entity_relation(name)
│   └── get_by_id(id) / get_by_ids(ids)
│
├── BaseGraphStorage
│   ├── has_node(node_id) / has_edge(src, tgt)
│   ├── upsert_node(node_id, data) / upsert_edge(src, tgt, data)
│   ├── delete_node(node_id) / remove_nodes(nodes)
│   ├── get_knowledge_graph(label, max_depth, max_nodes)
│   └── get_popular_labels(limit) / search_labels(query)
│
└── DocStatusStorage(BaseKVStorage)
    ├── get_status_counts()
    ├── get_docs_by_status(status)
    └── get_docs_paginated(page, page_size)
```

### 5.3 操作模块 (operate.py)

```python
# 核心函数
chunking_by_token_size()      # 文本分块
extract_entities()            # 实体/关系提取
merge_nodes_and_edges()        # 节点/边合并
kg_query()                    # 知识图谱查询
naive_query()                 # 朴素向量查询
rebuild_knowledge_from_chunks() # 从 chunk 重建知识
```

### 5.4 Prompt 模板 (prompt.py)

```python
PROMPTS = {
    # 实体提取
    "entity_extraction_system_prompt": LLM 角色定义
    "entity_extraction_user_prompt": 提取任务模板

    # 摘要生成
    "summarize_entity_descriptions": 实体描述摘要

    # 查询响应
    "rag_response": KG + Chunk 融合响应
    "naive_rag_response": 纯 Chunk 响应

    # 关键词提取
    "keywords_extraction": 高层/低层关键词
}
```

## 6. 查询模式详解

### 6.1 Mix 模式 (推荐)

```
Query
  │
  ▼
┌─────────────────┐
│ Keyword Extract │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Parallel Retrieval:                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Entities    │  │  Relations   │  │ Text Chunks  │      │
│  │  (Vector DB) │  │  (Vector DB) │  │  (Vector DB) │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                  │              │
│         ▼                 ▼                  ▼              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  KG Lookup   │  │  KG Lookup   │  │   Rerank    │      │
│  │  (Graph DB)  │  │  (Graph DB)  │  │ (Optional)  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Token Budget Management                                     │
│  - max_entity_tokens: 6000 (default)                        │
│  - max_relation_tokens: 8000 (default)                      │
│  - max_total_tokens: 30000 (default)                       │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  LLM Response Generation                                     │
│  PROMPTS["rag_response"] + context_data                     │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Token 预算控制

```python
@dataclass
class QueryParam:
    max_entity_tokens: int = 6000      # 实体上下文上限
    max_relation_tokens: int = 8000     # 关系上下文上限
    max_total_tokens: int = 30000       # 总 token 上限
    top_k: int = 60                     # KG 实体/关系数
    chunk_top_k: int = 20               # 初始 chunk 数
    enable_rerank: bool = True          # 启用重排序
```

## 7. LLM 集成

### 7.1 支持的 LLM 提供者 (llm/)

```
llm/
├── openai.py        # OpenAI GPT 系列
├── anthropic.py     # Anthropic Claude
├── azure_openai.py  # Azure OpenAI
├── ollama.py        # Ollama 本地模型
├── gemini.py        # Google Gemini
├── hf.py           # HuggingFace
├── bedrock.py      # AWS Bedrock
├── zhipu.py        # 智谱 GLM
├── lmdeploy.py     # LMDeploy
├── lollms.py       # LoLLMs
├── nvidia_openai.py # NVIDIA OpenAI
└── jina.py         # Jina AI
```

### 7.2 Embedding 函数

```python
@wrap_embedding_func_with_attrs(embedding_dim=1536, max_token_size=8192)
async def openai_embed(texts: list[str]) -> np.ndarray:
    return await openai_embed_func(texts, model="text-embedding-3-large")
```

## 8. 配置架构

### 8.1 配置文件示例 (config.yaml)

```yaml
working_dir: "./dickens"

# LLM 配置
llm:
  model_func: "anthropic"
  model_name: "MiniMax-M2.7"
  api_key: "..."
  base_url: "https://api.minimaxi.com/anthropic"

# Embedding 配置
embedding:
  provider: "ollama"
  model: "nomic-embed-text"
  dimension: 768

# 存储配置
storage:
  kv_storage: "JsonKVStorage"
  vector_storage: "NanoVectorDBStorage"
  graph_storage: "Neo4JStorage"
  doc_status_storage: "JsonDocStatusStorage"

# Neo4j 连接
neo4j:
  uri: "bolt://localhost:7687"
  username: "neo4j"
  password: "..."

# 分块配置
chunking:
  chunk_token_size: 1200
  chunk_overlap_token_size: 100
```

## 9. API 服务器 (api/)

```
api/
├── lightrag_server.py      # FastAPI 主服务器
├── routers/
│   ├── document_routes.py  # 文档操作 API
│   ├── query_routes.py     # 查询 API
│   ├── graph_routes.py    # 知识图谱 API
│   └── ollama_api.py       # Ollama 兼容 API
├── auth.py                 # 认证
├── passwords.py            # 密码管理
└── gunicorn_config.py      # Gunicorn 配置
```

## 10. 工作流程时序图

### 10.1 文档索引

```
Client          LightRAG         Storage
  │                │               │
  │──ainsert()────▶│               │
  │                │──chunking()──▶│
  │                │◀──────────────│
  │                │               │
  │                │─extract──────▶│ entities_vdb
  │                │─extract──────▶│ relationships_vdb
  │                │─upsert───────▶│ chunk_entity_relation_graph
  │                │─upsert───────▶│ entity_chunks
  │                │─upsert───────▶│ relation_chunks
  │                │─index_done───▶│ (persist)
  │◀──result───────│               │
  │                │               │
```

### 10.2 知识图谱查询

```
Client          LightRAG         Vector DB        Graph DB
  │                │                 │                │
  │──aquery()────▶│                 │                │
  │                │──keywords──────▶│                │
  │                │◀────────────────│                │
  │                │                 │                │
  │                │─query(top_k)───▶│                │
  │                │◀─entities───────│                │
  │                │                 │                │
  │                │─get_knowledge──▶│                │
  │                │◀─subgraph───────│                │
  │                │                 │                │
  │                │─rerank(if on)──▶│                │
  │                │◀─ranked────────│                │
  │                │                 │                │
  │                │─llm response───▶│                │
  │◀──answer───────│                 │                │
```

## 11. 关键设计模式

### 11.1 异步优先

所有存储操作和 LLM 调用都是异步的，使用 `async/await` 模式。

### 11.2 可插拔架构

通过抽象基类和动态加载，支持多种存储后端。

### 11.3 Token 预算管理

统一控制实体、关系、chunk 的 token 分配，避免超出 LLM 上下文限制。

### 11.4 Workspace 隔离

```python
rag1 = LightRAG(workspace="project_a")
rag2 = LightRAG(workspace="project_b")
# 数据完全隔离
```

### 11.5 LLM 缓存

```python
enable_llm_cache: bool = True              # 通用缓存
enable_llm_cache_for_entity_extract: bool = True  # 实体提取缓存
```

## 12. 性能优化

### 12.1 并发控制

```python
llm_model_max_async: int = 16        # LLM 并发数
embedding_func_max_async: int = 8     # Embedding 并发数
max_parallel_insert: int = 10          # 插入并发数
```

### 12.2 批处理

```python
embedding_batch_num: int = 10         # Embedding 批大小
```

### 12.3 重排序

```python
rerank_model_func: Callable           # 重排序模型
min_rerank_score: float = 0.0          # 重排序阈值
```
