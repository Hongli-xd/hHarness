"""Citation and Source Tracing Tool for historical research.

This tool enables historians to:
1. Insert citations linking claims to knowledge graph nodes
2. Trace claims back to their source documents
3. Track the provenance of historical assertions
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from ..agent import BaseTool, ToolExecutionContext, ToolResult

from ..lightrag import (
    CredibilityAnnotator,
    Citation,
    SourceCredibility,
    annotate_with_credibility,
    create_citation,
    get_annotator,
)


class CiteOperation(str, Enum):
    """Operations for the citation tool."""

    INSERT = "insert"  # Tag a claim with source citations
    TRACE = "trace"  # Find the source for a claim
    LIST = "list"  # List all citations
    ANNOTATE = "annotate"  # Add credibility annotation to a claim


class CiteInput(BaseModel):
    """Input schema for the Citation Tool."""

    operation: CiteOperation = Field(
        description="""Citation operation:
- insert: Tag a claim with KG node citations
- trace: Find sources for a given claim
- list: List all stored citations
- annotate: Add credibility annotation to a claim"""
    )
    claim: str | None = Field(
        default=None,
        description="Historical claim to cite or annotate",
    )
    kg_node_ids: list[str] | None = Field(
        default=None,
        description="Knowledge graph node IDs to cite (for insert operation)",
    )
    source_entities: list[str] | None = Field(
        default=None,
        description="Source entity names (alternative to kg_node_ids)",
    )
    credibility: SourceCredibility | None = Field(
        default=None,
        description="Source credibility level (一手文献/二手研究/争议性说法)",
    )
    source_type: str | None = Field(
        default=None,
        description="Type of source (e.g., 史书, 考古, 研究论文)",
    )
    period: str | None = Field(
        default=None,
        description="Historical period (e.g., 西汉, 唐代)",
    )
    notes: str | None = Field(
        default=None,
        description="Additional notes about this citation",
    )
    tags: list[str] | None = Field(
        default=None,
        description="Additional tags (e.g., 争议性, 待考证)",
    )
    claim_id: str | None = Field(
        default=None,
        description="Claim ID (for trace and list operations)",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of citations to list",
    )


class CiteTool(BaseTool):
    """引用追踪工具 - 管理历史文献引用和来源追溯。

该工具使历史研究Agent能够：
1. INSERT：插入引用，将历史论断与知识图谱节点关联
2. TRACE：追溯来源，查找支持某论断的证据
3. LIST：列出所有已存储的引用
4. ANNOTATE：为论断添加可信度标注

历史叙事必须始终标注来源。使用此工具确保：
- 所有论断都可追溯到原始文献
- 不同来源的可信度得到追踪
- 建立研究过程的引用数据库
"""

    name = "cite"
    description = """管理历史论断的引用，追溯其文献来源。

【四大操作】
1. insert（插入）：将历史论断与知识图谱节点关联添加引用
2. trace（追溯）：查找支持某论断的证据和来源
3. list（列表）：查看所有已存储的引用记录
4. annotate（标注）：为论断添加可信度等级标注

【可信度等级】
- 一手文献：事件同时代的原始记录
- 二手研究：后世学者的分析研究
- 争议性说法：学术界存在不同解读的论断

【使用场景】
- 生成历史叙事时确保论断有据可查
- 追溯某个观点的原始文献出处
- 追踪知识图谱中论断的可信度
"""
    input_model = CiteInput

    def get_schema_overrides(self) -> dict[str, Any]:
        """返回中文Schema描述"""
        return {
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["insert", "trace", "list", "annotate"],
                        "description": "操作类型：\n- insert：插入引用，将论断与KG节点关联\n- trace：追溯某论断的来源证据\n- list：列出所有已存储的引用\n- annotate：为论断添加可信度标注"
                    },
                    "claim": {
                        "type": "string",
                        "description": "历史论断内容\n例如：\"唐代藩镇割据源于安史之乱\""
                    },
                    "kg_node_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "知识图谱节点ID列表，用于insert操作\n例如：[\"entity_001\", \"relation_025\"]"
                    },
                    "source_entities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "来源实体名称列表（insert/annotate时使用）\n例如：[\"旧唐书\", \"资治通鉴\"]"
                    },
                    "credibility": {
                        "type": "string",
                        "enum": ["一手文献", "二手研究", "争议性说法", "未知"],
                        "description": "来源可信度等级：\n- 一手文献：事件同时代的第一手记录\n- 二手研究：后世学者的分析研究\n- 争议性说法：学术界有不同解读\n- 未知：无法确定可信度"
                    },
                    "source_type": {
                        "type": "string",
                        "description": "史料类型\n例如：史书、考古发现、研究论文、档案等"
                    },
                    "period": {
                        "type": "string",
                        "description": "历史时期\n例如：西汉、唐代、明代"
                    },
                    "notes": {
                        "type": "string",
                        "description": "关于此引用的补充说明\n例如：此说法存在争议，需进一步考证"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "标签列表\n例如：[\"争议性\", \"待考证\", \"重要\"]"
                    },
                    "claim_id": {
                        "type": "string",
                        "description": "论断ID，用于trace和list操作\n当需要精确查找某条已存储的引用时使用"
                    },
                    "limit": {
                        "type": "integer",
                        "default": 20,
                        "description": "list操作返回的最大引用数量，默认20条"
                    }
                },
                "required": ["operation"]
            }
        }

    def __init__(self, annotator: CredibilityAnnotator | None = None):
        """Initialize Citation Tool.

        Args:
            annotator: CredibilityAnnotator for storing citations
        """
        self.annotator = annotator or get_annotator()
        super().__init__()

    def is_read_only(self, arguments: CiteInput) -> bool:
        """Most operations are read-only except insert/annotate."""
        return arguments.operation in {CiteOperation.TRACE, CiteOperation.LIST}

    async def execute(
        self, arguments: CiteInput, context: ToolExecutionContext
    ) -> ToolResult:
        """Execute the citation operation."""
        try:
            if arguments.operation == CiteOperation.INSERT:
                return await self._insert_citation(arguments)
            elif arguments.operation == CiteOperation.TRACE:
                return await self._trace_source(arguments)
            elif arguments.operation == CiteOperation.LIST:
                return await self._list_citations(arguments)
            elif arguments.operation == CiteOperation.ANNOTATE:
                return await self._annotate_claim(arguments)
            else:
                return ToolResult(
                    output=f"Unknown operation: {arguments.operation}",
                    is_error=True,
                )
        except Exception as e:
            return ToolResult(
                output=f"Citation Error: {str(e)}",
                is_error=True,
            )

    async def _insert_citation(self, args: CiteInput) -> ToolResult:
        """Insert a new citation linking claim to sources."""
        if not args.claim:
            return ToolResult(
                output="claim is required for insert operation",
                is_error=True,
            )

        # Get node IDs
        kg_node_ids = args.kg_node_ids or []
        if args.source_entities and not kg_node_ids:
            # Use source entities as node IDs if not provided
            kg_node_ids = args.source_entities

        # Determine credibility
        credibility = args.credibility or SourceCredibility.UNKNOWN

        # Create citation
        citation = create_citation(
            claim=args.claim,
            kg_results={"node_ids": kg_node_ids} if kg_node_ids else None,
            credibility=credibility,
        )

        # Also store as annotation
        annotate_with_credibility(
            claim=args.claim,
            credibility=credibility,
            source_entities=args.source_entities,
            source_type=args.source_type,
            period=args.period,
            notes=args.notes,
            kg_node_ids=kg_node_ids,
            tags=args.tags,
        )

        # Format output
        output = "## Citation Inserted\n\n"
        output += f"**Claim**: {args.claim}\n"
        output += f"**Credibility**: [{credibility.value}]\n"
        if kg_node_ids:
            output += f"**Sources**: {', '.join(f'[{n}]' for n in kg_node_ids)}\n"
        if args.source_type:
            output += f"**Source Type**: {args.source_type}\n"
        if args.period:
            output += f"**Period**: {args.period}\n"
        output += f"\n**Citation**: {citation.format('inline')}"

        return ToolResult(output=output)

    async def _trace_source(self, args: CiteInput) -> ToolResult:
        """Find sources for a given claim."""
        if not args.claim and not args.claim_id:
            return ToolResult(
                output="Either claim or claim_id is required for trace operation",
                is_error=True,
            )

        # Find annotations matching the claim
        if args.claim_id:
            annotation = self.annotator.get_annotation(args.claim_id)
            if annotation:
                output = self._format_annotation(annotation)
            else:
                output = f"Citation not found: {args.claim_id}"
        else:
            # Search by claim text
            annotations = self.annotator.list_annotations(limit=100)
            matches = [
                a for a in annotations
                if args.claim and args.claim in a.claim_text
            ]
            if matches:
                output = f"Found {len(matches)} matching citation(s):\n\n"
                output += "\n\n".join(self._format_annotation(a) for a in matches[:5])
            else:
                output = f"No citations found for: {args.claim}"

        return ToolResult(output=output)

    async def _list_citations(self, args: CiteInput) -> ToolResult:
        """List all stored citations."""
        annotations = self.annotator.list_annotations(limit=args.limit)

        if not annotations:
            output = "No citations stored yet.\n\n"
            output += "Use 'insert' operation to add citations for historical claims."
        else:
            output = f"# Stored Citations ({len(annotations)})\n\n"
            for i, ann in enumerate(annotations, 1):
                output += f"{i}. {self._format_annotation(ann)}\n\n"

        return ToolResult(output=output)

    async def _annotate_claim(self, args: CiteInput) -> ToolResult:
        """Add credibility annotation to a claim."""
        if not args.claim:
            return ToolResult(
                output="claim is required for annotate operation",
                is_error=True,
            )

        credibility = args.credibility or SourceCredibility.UNKNOWN

        annotated = annotate_with_credibility(
            claim=args.claim,
            credibility=credibility,
            source_entities=args.source_entities,
            source_type=args.source_type,
            period=args.period,
            notes=args.notes,
            kg_node_ids=args.kg_node_ids,
            tags=args.tags,
        )

        output = "## Claim Annotated\n\n"
        output += f"**Claim**: {annotated.claim}\n"
        output += f"**Credibility**: [{annotated.credibility.value}]\n"
        if annotated.source_type:
            output += f"**Source Type**: {annotated.source_type}\n"
        if annotated.period:
            output += f"**Period**: {annotated.period}\n"
        if annotated.notes:
            output += f"**Notes**: {annotated.notes}\n"

        return ToolResult(output=output)

    def _format_annotation(self, annotation) -> str:
        """Format an annotation for display."""
        cred_emoji = {
            "一手文献": "📜",
            "二手研究": "📚",
            "争议性说法": "⚠️",
            "未知": "❓",
        }.get(annotation.credibility, "📄")

        lines = [
            f"{cred_emoji} **Claim**: {annotation.claim_text}",
            f"   Credibility: [{annotation.credibility}]",
        ]
        if annotation.source_entities:
            lines.append(f"   Sources: {', '.join(annotation.source_entities)}")
        if annotation.source_type:
            lines.append(f"   Type: {annotation.source_type}")
        if annotation.period:
            lines.append(f"   Period: {annotation.period}")
        if annotation.notes:
            lines.append(f"   Notes: {annotation.notes}")

        return "\n".join(lines)
