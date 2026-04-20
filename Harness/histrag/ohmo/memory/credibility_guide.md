# Source Credibility Guide

## Credibility Classification System

This guide defines the credibility levels used to annotate historical claims in research.

### 一手文献 (Primary Sources)

**Definition**: Sources created at the time of the events described, by participants or witnesses.

**Characteristics**:
- Contemporary to the events
- Created by people with direct knowledge
- May have biases of the time and author

**Examples**:
- 史书 (Historiographical works): 《史记》《汉书》《资治通鉴》
- 档案 (Archival documents): 政府文书, 契约, 奏章
- 金石 (Inscriptions): 碑刻, 青铜器铭文
- 考古 (Archaeological): 出土文物, 遗址

**Tag**: [一手文献]

### 二手研究 (Secondary Sources)

**Definition**: Later scholarship that analyzes, interprets, or builds upon primary sources.

**Characteristics**:
- Created after the events
- May draw on multiple primary sources
- Represents scholarly interpretation

**Examples**:
- 学术专著 (Academic monographs)
- 期刊论文 (Journal articles)
- 教科书 (Textbooks)
- 编年史整理 (Compiled chronologies)

**Tag**: [二手研究]

### 争议性说法 (Disputed Claims)

**Definition**: Historical claims where scholars disagree on the facts or interpretations.

**Characteristics**:
- Multiple competing interpretations exist
- Evidence is ambiguous or contradictory
- Active scholarly debate continues

**Examples**:
- 秦始皇焚书坑儒的具体规模
- 安史之乱的经济根源
- 明清资本主义萌芽问题

**Tag**: [争议性说法]

**Note**: When encountering disputed claims, always present the main competing interpretations and their key evidence.

## Annotation Guidelines

### When to Annotate

1. **Every factual claim** should be traceable to a source
2. **Interpretation** should be labeled as such
3. **Disputed claims** must be explicitly labeled as disputed

### How to Annotate

Use the `cite` tool to:
```
claim: [the historical claim]
credibility: [primary/secondary/disputed]
source_entities: [relevant sources]
notes: [any additional context]
```

### Credibility in Narrative

When generating historical narrative, use inline tags:

```
According to Sima Qian's Records of the Grand Historian [一手文献][KG:entity_史记],
the battle occurred in 208 BCE...
```

## Quality Checks

Before presenting any historical claim:

1. ✅ Is the source primary or secondary?
2. ✅ Is the claim supported by multiple sources?
3. ✅ Is this a contested interpretation?
4. ✅ Have I cited the source explicitly?
