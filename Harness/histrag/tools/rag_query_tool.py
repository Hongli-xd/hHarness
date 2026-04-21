"""General RAG Query Tool for historical research.

This tool provides full-text RAG query capabilities using LightRAG,
complementing the KG Query Tool for when you need to search through
the full text corpus.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from ..agent import BaseTool, ToolExecutionContext, ToolResult

from ..lightrag import LightRAGClient


class RAGMode(str, Enum):
    """Query modes for RAG search."""

    LOCAL = "local"  # Context-dependent, specific entities
    GLOBAL = "global"  # Community-based, broad knowledge
    HYBRID = "hybrid"  # Combines local and global
    NAIVE = "naive"  # Direct vector search, no graph
    MIX = "mix"  # KG + vector with reranking (recommended)


class RAGQueryInput(BaseModel):
    """Input schema for the RAG Query Tool."""

    query: str = Field(
        description="Research question or topic to query"
    )
    mode: RAGMode = Field(
        default=RAGMode.MIX,
        description="Query mode: local (specific), global (broad), hybrid, naive (vector only), mix (recommended)"
    )
    top_k: int = Field(
        default=60,
        ge=1,
        le=200,
        description="Number of knowledge graph entities/relations to retrieve"
    )
    chunk_top_k: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of text chunks to retrieve"
    )
    stream: bool = Field(
        default=False,
        description="Whether to stream the LLM response"
    )


class RAGQueryTool(BaseTool):
    """通用RAG查询工具，用于历史研究。

提供全文检索增强生成能力，适合搜索整个文档语料库，
而不仅仅是实体关系图谱。

【五种检索模式】
- mix（推荐）：结合知识图谱和向量检索，重排序后返回
- hybrid：混合本地检索和全局检索
- local：聚焦特定实体及其直接上下文
- global：基于社区的广域知识检索
- naive：纯向量相似度搜索

【返回内容】
- LLM生成的回答
- 附带源文档片段引用
"""
    name = "rag_query"
    description = """RAG（检索增强生成）查询工具，用于全文历史研究。

【功能说明】
对历史文档语料库进行全文检索，由LLM生成综合回答。

【必须传入的参数】
- query：必须填入【当前用户问题原文】，不能为空，不能省略

【五种检索模式详解】
1. mix（推荐）：融合知识图谱+向量检索+重排序，效果最均衡
2. hybrid：结合局部检索（精准）和全局检索（广度）
3. local：专注特定实体的上下文，精准但范围窄
4. global：基于实体社区的广域检索，适合宏观问题
5. naive：纯向量相似度，速度快但忽略图结构

【返回内容】
LLM生成的回答文本，附带源文档片段的引用和出处信息

【使用场景】
- 需要LLM综合多份文档回答复杂历史问题
- 研究跨越多个主题或时期的历史问题
- 需要理解文档之间的语义关联
"""
    input_model = RAGQueryInput

    def get_schema_overrides(self) -> dict[str, Any]:
        """返回中文Schema描述"""
        return {
            "description": self.description,
        }

    def __init__(self, rag_client: LightRAGClient):
        """Initialize RAG Query Tool.

        Args:
            rag_client: LightRAG client for queries
        """
        self.rag_client = rag_client
        super().__init__()

    def is_read_only(self, arguments: RAGQueryInput) -> bool:
        """RAG queries are always read-only."""
        return True

    async def execute(
        self, arguments: RAGQueryInput, context: ToolExecutionContext
    ) -> ToolResult:
        """Execute the RAG query."""
        try:
            # Fallback to original_question if query not provided
            query = arguments.query
            if not query:
                query = context.metadata.get("original_question")
            if not query or query is None:
                return ToolResult(
                    output="query is required",
                    is_error=True,
                )

            result = await self.rag_client.aquery(
                query=str(query),
                mode=arguments.mode.value,
                top_k=arguments.top_k,
                chunk_top_k=arguments.chunk_top_k,
                stream=arguments.stream,
            )

            # Handle streaming response
            if arguments.stream:
                # For streaming, accumulate chunks
                chunks = []
                async for chunk in result:
                    chunks.append(chunk)
                output = "".join(chunks)
            else:
                output = str(result)

            return ToolResult(output=output)

        except Exception as e:
            return ToolResult(
                output=f"RAG Query Error: {str(e)}",
                is_error=True,
            )


class RAGDataQueryInput(BaseModel):
    """Input schema for RAG data-only query (no LLM generation)."""

    query: str = Field(
        description="Research question or topic"
    )
    mode: RAGMode = Field(
        default=RAGMode.MIX,
        description="Query mode"
    )
    top_k: int = Field(
        default=60,
        ge=1,
        le=200,
        description="Number of KG entities to retrieve"
    )
    chunk_top_k: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of text chunks to retrieve"
    )


class RAGDataQueryTool(BaseTool):
    """RAG数据查询工具 - 返回结构化数据，不进行LLM生成。

当需要获取原始上下文而不是LLM综合回答时使用，
适合Agent自己处理数据或进行进一步分析。
"""

    name = "rag_data_query"
    description = """RAG数据查询工具 - 仅返回检索到的原始数据，不进行LLM生成。

【必须传入的参数】
- query：必须填入【当前用户问题原文】，不能为空，不能省略

【功能说明】
直接返回从知识图谱和文档库检索到的实体、关系和文本片段，
不经过LLM综合处理。

【返回内容】
- entities：检索到的知识图谱实体列表（包含名称、类型、描述）
- relations：实体间关系列表（包含关系描述）
- chunks：文本片段列表（包含原文和出处）

【使用场景】
- Agent需要对原始数据进行二次处理或分析
- 构建自定义的知识整理流程
- 获取数据后进行结构化输出或进一步推理
"""
    input_model = RAGDataQueryInput

    def get_schema_overrides(self) -> dict[str, Any]:
        """返回中文Schema描述"""
        return {
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "【必填】研究问题或查询主题，直接填入用户原始问题，不能为空\n例如：\"唐代有哪些道制\"、\"安史之乱的起因\""
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["local", "global", "hybrid", "naive", "mix"],
                        "description": "检索模式（与rag_query相同）：\n- mix（推荐）：融合KG和向量检索\n- hybrid：混合本地+全局\n- local：聚焦特定实体上下文\n- global：社区广域检索\n- naive：纯向量搜索"
                    },
                    "top_k": {
                        "type": "integer",
                        "default": 60,
                        "description": "从知识图谱检索的实体/关系数量上限"
                    },
                    "chunk_top_k": {
                        "type": "integer",
                        "default": 20,
                        "description": "从文本库检索的文档片段数量上限"
                    }
                },
                "required": ["query"]
            }
        }
    input_model = RAGDataQueryInput

    def __init__(self, rag_client: LightRAGClient):
        """Initialize RAG Data Query Tool."""
        self.rag_client = rag_client
        super().__init__()

    def is_read_only(self, arguments: RAGDataQueryInput) -> bool:
        return True

    async def execute(
        self, arguments: RAGDataQueryInput, context: ToolExecutionContext
    ) -> ToolResult:
        """Execute the RAG data query (no LLM)."""
        try:
            query = arguments.query
            if not query:
                query = context.metadata.get("original_question")
            if not query:
                return ToolResult(
                    output="query is required",
                    is_error=True,
                )

            result = await self.rag_client.aquery_data(
                query=arguments.query,
                mode=arguments.mode.value,
                top_k=arguments.top_k,
                chunk_top_k=arguments.chunk_top_k,
            )

            # Format the structured result
            output = self._format_rag_data(result)

            return ToolResult(output=output)

        except Exception as e:
            return ToolResult(
                output=f"RAG Data Query Error: {str(e)}",
                is_error=True,
            )

    def _format_rag_data(self, data: dict) -> str:
        """Format structured RAG data for display."""
        lines = ["# RAG Query Results\n"]

        # Entities
        if "entities" in data and data["entities"]:
            lines.append(f"## Entities ({len(data['entities'])})\n")
            for entity in data["entities"][:20]:  # Limit display
                name = entity.get("entity_name", "unknown")
                desc = entity.get("description", "")[:100]
                lines.append(f"- **{name}**: {desc}...")
            if len(data["entities"]) > 20:
                lines.append(f"  ... and {len(data['entities']) - 20} more")

        # Relations
        if "relations" in data and data["relations"]:
            lines.append(f"\n## Relations ({len(data['relations'])})\n")
            for rel in data["relations"][:20]:
                src = rel.get("src_tgt", [rel.get("source", ""), rel.get("target", "")])
                desc = rel.get("description", "")[:80]
                lines.append(f"- {' → '.join(src)}: {desc}...")
            if len(data["relations"]) > 20:
                lines.append(f"  ... and {len(data['relations']) - 20} more")

        # Chunks
        if "chunks" in data and data["chunks"]:
            lines.append(f"\n## Text Chunks ({len(data['chunks'])})\n")
            for i, chunk in enumerate(data["chunks"][:10], 1):
                if isinstance(chunk, dict):
                    text = chunk.get("chunk_text", str(chunk))[:200]
                else:
                    text = str(chunk)[:200]
                lines.append(f"{i}. {text}...")
            if len(data["chunks"]) > 10:
                lines.append(f"\n... and {len(data['chunks']) - 10} more chunks")

        return "\n".join(lines)
