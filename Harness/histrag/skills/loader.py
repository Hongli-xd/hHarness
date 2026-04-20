"""Skills loader for historical methodology skills.

This module provides integration with OpenHarness's skills system,
loading historical methodology skills from the histrag/skills/ directory.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openharness.skills import SkillRegistry

# Default skills directory relative to this file
DEFAULT_SKILLS_DIR = Path(__file__).parent


def load_historical_skill_registry(
    cwd: str | Path | None = None,
) -> "SkillRegistry":
    """Load historical methodology skills.

    This function integrates with OpenHarness's skill loading mechanism.
    It loads skills from the histrag/skills/ directory and returns
    a SkillRegistry that can be merged with the OpenHarness registry.

    Args:
        cwd: Current working directory (passed to OpenHarness's loader)

    Returns:
        SkillRegistry with historical methodology skills loaded
    """
    from openharness.skills import load_skill_registry

    skills_dir = DEFAULT_SKILLS_DIR

    # Load using OpenHarness's loader with extra skill directories
    registry = load_skill_registry(
        cwd=str(cwd) if cwd else ".",
        extra_skill_dirs=[str(skills_dir)],
    )

    return registry


__all__ = [
    "load_historical_skill_registry",
    "DEFAULT_SKILLS_DIR",
]
