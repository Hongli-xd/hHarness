"""Historian system prompts for the research agent.

This module provides system prompts loaded from:
- ohmo/soul.md: Core identity and beliefs
- ohmo/identity.md: Agent identity definition
- ohmo/memory/: Persistent memory files
- skills/: Historical methodology skills
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


# Default paths relative to this module
OIMO_DIR = Path(__file__).parent.parent / "ohmo"
SKILLS_DIR = Path(__file__).parent.parent / "skills"


def _load_ohmo_file(filename: str) -> str | None:
    """Load a file from the ohmo directory."""
    path = OIMO_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def _load_skills_section() -> str | None:
    """Build the skills section for the system prompt."""
    skills_dir = SKILLS_DIR
    if not skills_dir.exists():
        return None

    skill_files = sorted(skills_dir.glob("*.md"))
    if not skill_files:
        return None

    lines = [
        "# Historical Research Skills",
        "",
        "The following research methodology skills are available. "
        "When relevant to your investigation, apply these methods.",
        "",
    ]

    for skill_path in skill_files:
        name = skill_path.stem  # filename without extension
        # Get first line as description
        content = skill_path.read_text(encoding="utf-8")
        first_line = content.split("\n")[0].strip()
        if first_line.startswith("# "):
            description = first_line[2:].strip()
        else:
            description = first_line[:100] if first_line else name
        lines.append(f"- **{name}**: {description}")

    return "\n".join(lines)


def _load_memory_section() -> str | None:
    """Load memory files from ohmo/memory/ directory."""
    memory_dir = OIMO_DIR / "memory"
    if not memory_dir.exists():
        return None

    memory_files = sorted(memory_dir.glob("*.md"))
    if not memory_files:
        return None

    # Filter out MEMORY.md index if it exists
    memory_files = [f for f in memory_files if f.name != "MEMORY.md"]

    if not memory_files:
        return None

    lines = [
        "# Research Memory",
        "",
        "The following persistent research notes are available:",
        "",
    ]

    for memory_path in memory_files:
        name = memory_path.stem
        # Read first paragraph as description
        content = memory_path.read_text(encoding="utf-8")
        lines.append(f"- **{name}**")

    lines.append("")
    lines.append("Key principles from memory:")
    lines.append("")

    for memory_path in memory_files:
        content = memory_path.read_text(encoding="utf-8")
        # Get first 200 chars of content
        first_content = content[:200].strip()
        if first_content:
            lines.append(f"> {first_content}...")

    return "\n".join(lines)


def _build_identity_section() -> str:
    """Build the identity section from soul.md and identity.md."""
    parts = []

    soul = _load_ohmo_file("soul.md")
    if soul:
        parts.append(soul)

    identity = _load_ohmo_file("identity.md")
    if identity:
        parts.append(identity)

    return "\n\n".join(parts) if parts else _get_fallback_identity()


def _get_fallback_identity() -> str:
    """Fallback identity if ohmo files are missing."""
    return """\
# SOUL.md - Historical Research Agent

You are HistRAG, a historical research AI assistant.

## Core Beliefs

- **史料是历史的唯一法庭** — 原始史料是历史主张的最终裁判
- **因果链高于事件序列** — 因果链比事件编年更重要
- **争议是学术的生命** — 学者之间的分歧是健康的

## Identity

- Name: HistRAG
- Type: Historical Research Agent
- Style: Academic, rigorous, impartial, time-sensitive
"""


def build_historian_system_prompt(
    extra_prompt: str | None = None,
    cwd: str | Path | None = None,
    include_skills: bool = True,
    include_memory: bool = True,
) -> str:
    """Build the historian system prompt from ohmo files.

    Args:
        extra_prompt: Additional custom instructions
        cwd: Current working directory for context
        include_skills: Whether to include skills section
        include_memory: Whether to include memory section

    Returns:
        Complete system prompt string
    """
    sections = []

    # 1. Core identity from ohmo/soul.md + ohmo/identity.md
    identity_section = _build_identity_section()
    if identity_section:
        sections.append(identity_section)

    # 2. Research methodology (from hardcoded fallback for now)
    methodology = _get_methodology_section()
    sections.append(methodology)

    # 3. Skills section
    if include_skills:
        skills_section = _load_skills_section()
        if skills_section:
            sections.append(skills_section)

    # 4. Memory section
    if include_memory:
        memory_section = _load_memory_section()
        if memory_section:
            sections.append(memory_section)

    # 5. Additional instructions
    if extra_prompt:
        sections.append(f"\n\n## Additional Instructions\n\n{extra_prompt}")

    # 6. Environment info
    env_parts = ["## Environment\n"]
    env_parts.append(f"- Working directory: {cwd or '.'}")
    env_parts.append(f"- Date: {os.environ.get('TODAY', '2026-04-20')}")
    env_parts.append("- Historical Research Context: Enabled")
    sections.append("\n".join(env_parts))

    return "\n\n".join(sections)


def _get_methodology_section() -> str:
    """Get the research methodology section."""
    return """\
## Research Methodology

### Causal Chain Analysis
- Always trace the chain of causes and effects behind historical events
- Distinguish between immediate triggers and structural conditions
- Consider multiple causation rather than single-cause explanations

### Source Criticism (史料批判)
- Evaluate sources for authenticity, reliability, and bias
- Consider the context in which sources were created
- Recognize that all sources are shaped by their time and perspective

### Temporal Context (时间语境)
- Interpret historical actors' decisions within their contemporary context
- Avoid anachronism — do not judge past actions by modern standards
- Consider the longue durée when relevant

### Evidence and Argumentation (实证与论证)
- Ground every claim in specific evidence
- Distinguish between facts, interpretations, and speculations
- Build arguments that can be verified and challenged

### Handling Controversy
- Present MAIN POSITIONS without stating one as definitively correct
- Acknowledge STRENGTHS and WEAKNESSES of each interpretation
- Cite specific scholars or schools when possible
- Use hedging appropriately: "The evidence suggests...", "Scholars generally agree..."

## Citation Standards

1. **Inline Citations**: Use [KG:entity_name] format for knowledge graph citations
2. **Source Credibility Tags**:
   - [一手文献] - Primary source, contemporary to events
   - [二手研究] - Secondary source, analysis of primary sources
   - [争议性说法] - Disputed claim with multiple interpretations
3. **Example**: "The battle occurred in 208 BCE [KG:楚汉战争], primarily recorded in [一手文献][KG:史记]"

## Research Workflow

When investigating a historical question:
1. **For general questions** (e.g., "唐代道制有哪些变化？") → use `rag_query` with mode="mix"
2. Use `cite` to track sources and add credibility annotations
3. Synthesize findings into a coherent narrative with proper citations
"""


def build_research_context_prompt(
    research_topic: str | None = None,
    time_period: str | None = None,
    sources: list[str] | None = None,
) -> str:
    """Build context prompt for a specific research topic."""
    parts = ["## Research Context"]

    if research_topic:
        parts.append(f"**Topic**: {research_topic}")

    if time_period:
        parts.append(f"**Time Period**: {time_period}")

    if sources:
        parts.append(f"**Primary Sources**: {', '.join(sources)}")

    return "\n".join(parts)
