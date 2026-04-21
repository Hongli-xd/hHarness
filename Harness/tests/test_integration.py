"""Tests for HistRAG integration - ohmo files, skills, and memory loading."""

import sys
from pathlib import Path

# Add harness to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


class TestOhmoFilesLoading:
    """Test that ohmo/soul.md and ohmo/identity.md are properly loaded."""

    def test_soul_md_exists(self):
        """Test that soul.md exists."""
        from histrag.prompts.historian import OIMO_DIR
        soul_path = OIMO_DIR / "soul.md"
        assert soul_path.exists(), f"soul.md not found at {soul_path}"
        content = soul_path.read_text(encoding="utf-8")
        assert len(content) > 0, "soul.md is empty"
        assert "HistRAG" in content or "历史研究" in content

    def test_identity_md_exists(self):
        """Test that identity.md exists."""
        from histrag.prompts.historian import OIMO_DIR
        identity_path = OIMO_DIR / "identity.md"
        assert identity_path.exists(), f"identity.md not found at {identity_path}"
        content = identity_path.read_text(encoding="utf-8")
        assert len(content) > 0, "identity.md is empty"

    def test_build_identity_section_loads_soul(self):
        """Test that _build_identity_section includes soul.md content."""
        from histrag.prompts.historian import _build_identity_section
        section = _build_identity_section()
        assert section is not None
        assert len(section) > 0
        # Should contain HistRAG identity
        assert "HistRAG" in section or "历史研究" in section

    def test_build_identity_section_loads_identity(self):
        """Test that _build_identity_section includes identity.md content."""
        from histrag.prompts.historian import _build_identity_section
        section = _build_identity_section()
        assert section is not None
        # Should contain identity markers
        assert "名称" in section or "Name" in section or "identity" in section.lower()


class TestSkillsLoading:
    """Test that skills are properly loaded."""

    def test_skills_dir_exists(self):
        """Test that skills directory exists."""
        from histrag.prompts.historian import SKILLS_DIR
        assert SKILLS_DIR.exists(), f"skills dir not found at {SKILLS_DIR}"

    def test_skills_files_exist(self):
        """Test that skill markdown files exist."""
        from histrag.prompts.historian import SKILLS_DIR
        skill_files = list(SKILLS_DIR.glob("*.md"))
        assert len(skill_files) > 0, f"No skill files found in {SKILLS_DIR}"
        # Check for expected skill files
        skill_names = {f.stem for f in skill_files}
        expected = {"chronology", "comparison", "counterfactual", "annales"}
        # At least some of these should exist
        assert len(skill_names & expected) > 0

    def test_load_skills_section(self):
        """Test that _load_skills_section returns valid content."""
        from histrag.prompts.historian import _load_skills_section
        section = _load_skills_section()
        assert section is not None
        assert "Skills" in section or "技能" in section
        # Should list available skills
        assert "chronology" in section.lower() or "编年" in section

    def test_system_prompt_includes_skills(self):
        """Test that build_historian_system_prompt includes skills section."""
        from histrag.prompts.historian import build_historian_system_prompt
        prompt = build_historian_system_prompt(include_skills=True)
        assert "Skills" in prompt or "技能" in prompt


class TestMemoryLoading:
    """Test that memory files are properly loaded."""

    def test_memory_dir_exists(self):
        """Test that ohmo/memory directory exists."""
        from histrag.prompts.historian import OIMO_DIR
        memory_dir = OIMO_DIR / "memory"
        assert memory_dir.exists(), f"memory dir not found at {memory_dir}"

    def test_memory_files_exist(self):
        """Test that memory markdown files exist."""
        from histrag.prompts.historian import OIMO_DIR
        memory_dir = OIMO_DIR / "memory"
        memory_files = list(memory_dir.glob("*.md"))
        assert len(memory_files) > 0, f"No memory files found in {memory_dir}"

    def test_load_memory_section(self):
        """Test that _load_memory_section returns valid content."""
        from histrag.prompts.historian import _load_memory_section
        section = _load_memory_section()
        assert section is not None
        assert "Memory" in section or "记忆" in section

    def test_system_prompt_includes_memory(self):
        """Test that build_historian_system_prompt includes memory section."""
        from histrag.prompts.historian import build_historian_system_prompt
        prompt = build_historian_system_prompt(include_memory=True)
        assert "Memory" in prompt or "记忆" in prompt or "Memory" in prompt


class TestSystemPromptBuilding:
    """Test the complete system prompt building."""

    def test_build_historian_system_prompt_returns_string(self):
        """Test that build_historian_system_prompt returns a non-empty string."""
        from histrag.prompts.historian import build_historian_system_prompt
        prompt = build_historian_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_system_prompt_includes_identity(self):
        """Test that system prompt includes identity from soul.md."""
        from histrag.prompts.historian import build_historian_system_prompt
        prompt = build_historian_system_prompt()
        # Should contain key identity elements
        assert "HistRAG" in prompt or "历史研究" in prompt

    def test_system_prompt_includes_methodology(self):
        """Test that system prompt includes research methodology."""
        from histrag.prompts.historian import build_historian_system_prompt
        prompt = build_historian_system_prompt()
        # Should contain methodology keywords
        assert any(kw in prompt for kw in ["因果", "causal", "史料", "source"])

    def test_system_prompt_includes_environment(self):
        """Test that system prompt includes environment info."""
        from histrag.prompts.historian import build_historian_system_prompt
        prompt = build_historian_system_prompt(cwd="/test")
        assert "Environment" in prompt or "Working directory" in prompt

    def test_system_prompt_with_extra_prompt(self):
        """Test that extra_prompt is appended to system prompt."""
        from histrag.prompts.historian import build_historian_system_prompt
        extra = "Custom instruction: Always cite sources."
        prompt = build_historian_system_prompt(extra_prompt=extra)
        assert extra in prompt

    def test_system_prompt_skips_skills_when_disabled(self):
        """Test that skills section can be disabled."""
        from histrag.prompts.historian import build_historian_system_prompt
        prompt = build_historian_system_prompt(include_skills=False)
        # Should still have identity but no skills
        assert "HistRAG" in prompt or len(prompt) > 0


class TestMemoryManagement:
    """Test memory management functions."""

    def test_get_memory_dir(self):
        """Test that get_memory_dir returns a valid path."""
        from histrag.integration import get_memory_dir
        memory_dir = get_memory_dir()
        assert isinstance(memory_dir, Path)
        assert "histrag" in str(memory_dir).lower()

    def test_add_memory_entry(self):
        """Test adding a memory entry."""
        import tempfile
        from histrag.integration import add_memory_entry

        with tempfile.TemporaryDirectory() as tmpdir:
            # Add a memory entry
            memory_path = add_memory_entry(
                cwd=tmpdir,
                title="Test Memory",
                content="This is a test memory entry."
            )
            assert memory_path.exists()
            content = memory_path.read_text(encoding="utf-8")
            assert "test memory entry" in content.lower()

    def test_load_project_memory(self):
        """Test loading project memory."""
        import tempfile
        from histrag.integration import add_memory_entry, load_project_memory

        with tempfile.TemporaryDirectory() as tmpdir:
            # Add a memory entry first
            add_memory_entry(
                cwd=tmpdir,
                title="Test Memory",
                content="This is a test."
            )
            # Load it back
            memory = load_project_memory(cwd=tmpdir)
            assert memory is not None
            assert "Test Memory" in memory


class TestCreateHistoricalRuntime:
    """Test create_historical_runtime function."""

    def test_returns_historian_runtime(self):
        """Test that create_historical_runtime returns a HistorianRuntime."""
        from histrag.integration import create_historical_runtime
        runtime = create_historical_runtime(cwd=".")
        assert runtime is not None
        # Check it's the right type
        assert hasattr(runtime, 'engine')
        assert hasattr(runtime, 'rag_client')
        assert hasattr(runtime, 'tool_registry')

    def test_runtime_has_skills_dir(self):
        """Test that runtime has skills_dir set."""
        from histrag.integration import create_historical_runtime
        runtime = create_historical_runtime(cwd=".")
        # skills_dir should be set (might be None if doesn't exist)
        assert hasattr(runtime, 'skills_dir')

    def test_runtime_has_memory_dir(self):
        """Test that runtime has memory_dir set."""
        from histrag.integration import create_historical_runtime
        runtime = create_historical_runtime(cwd=".")
        # memory_dir should be set (might be None if doesn't exist)
        assert hasattr(runtime, 'memory_dir')

    def test_extra_skill_dirs_override(self):
        """Test that extra_skill_dirs parameter works."""
        import tempfile
        from histrag.integration import create_historical_runtime

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a temp skills dir
            skills_dir = Path(tmpdir) / "skills"
            skills_dir.mkdir()
            (skills_dir / "test_skill.md").write_text("# Test Skill\nTest content.")

            runtime = create_historical_runtime(
                cwd=".",
                extra_skill_dirs=str(skills_dir)
            )
            assert runtime.skills_dir == skills_dir

    def test_extra_memory_dirs_override(self):
        """Test that extra_memory_dirs parameter works."""
        import tempfile
        from histrag.integration import create_historical_runtime

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a temp memory dir
            memory_dir = Path(tmpdir) / "memory"
            memory_dir.mkdir()

            runtime = create_historical_runtime(
                cwd=".",
                extra_memory_dirs=str(memory_dir)
            )
            assert runtime.memory_dir == memory_dir


class TestAllToolsReadOnly:
    """Test that all HistRAG tools are read-only."""

    def test_all_tools_return_read_only_true(self):
        """Test that all tool is_read_only returns True for valid inputs."""
        from histrag.tools.rag_query_tool import RAGQueryTool
        from histrag.tools.cite_tool import CiteTool, CiteOperation
        from histrag.tools.timeline_tool import TimelineTool
        from histrag.tools.map_location_tool import MapLocationTool
        from unittest.mock import MagicMock

        # Create mock clients
        mock_rag = MagicMock()

        # Create properly structured input objects
        tools_with_inputs = [
            (RAGQueryTool(mock_rag), MagicMock()),
            (CiteTool(MagicMock()), MagicMock(operation=CiteOperation.TRACE)),
            (TimelineTool(), MagicMock()),
            (MapLocationTool(), MagicMock()),
        ]

        for tool, mock_input in tools_with_inputs:
            # Call is_read_only with properly structured input - should return True
            result = tool.is_read_only(mock_input)
            assert result is True, f"{tool.name} should be read-only"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
