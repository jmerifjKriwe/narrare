"""Data types for prompt management.

Extracted from management.py per RULE-04 (modularize, don't compress).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class PromptInfo:
    """Metadata for a single prompt."""

    prompt_id: str  # "{category}/{language}/{mode}"
    name: str
    category: str
    language: str
    mode: str
    source: str  # "bundled", "project", "user"
    has_override: bool
    prompt_version: str
    is_overridden: bool


@dataclass(frozen=True, slots=True)
class PromptDetail:
    """Full prompt content with metadata."""

    prompt_id: str
    content: str
    base_content: str
    source: str
    is_overridden: bool
    variables: list[str]
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CascadePath:
    """A single level in the prompt cascade."""

    level: str  # "project", "user", "bundled", "bundled_en"
    path: Path
    exists: bool


@dataclass(frozen=True, slots=True)
class UpdateInfo:
    """Information about a prompt with available updates."""

    prompt_id: str
    override_version: str
    current_bundled_version: str
