"""Prompt variable provenance/security taxonomy helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class VariableProvenance(StrEnum):
    """Source/precedence class for prompt variables (INFRA-012)."""

    CURRENT_AUTHOR_INSTRUCTION = "current_author_instruction"
    PROJECT_WRITING_PROFILE = "project_writing_profile"
    SCENE_STORY_PLAN = "scene_story_plan"
    CURATED_KB = "curated_kb"
    LEARNED_MEMORY = "learned_memory"
    GENERATED_SUGGESTION = "generated_suggestion"
    SYSTEM_GENERATED = "system_generated"
    FEATURE_DYNAMIC = "feature_dynamic"


class VariableSecurity(StrEnum):
    """Template-level security requirement for a prompt variable."""

    XML_REQUIRED = "xml_required"
    XML_SECTION_REQUIRED = "xml_section_required"
    LABEL_REQUIRED = "label_required"
    GENERATED_LABEL_REQUIRED = "generated_label_required"
    SYSTEM_ONLY = "system_only"


@dataclass(frozen=True, slots=True)
class VariableClassification:
    """Governed variable provenance/security metadata."""

    name: str
    provenance: VariableProvenance
    security: VariableSecurity


def build_variable_classifications(
    user_content_vars: frozenset[str],
    system_vars: frozenset[str],
    feature_dynamic_vars: frozenset[str],
) -> dict[str, VariableClassification]:
    """Build complete provenance/security metadata for registered variables."""
    base = {
        **{
            name: VariableClassification(
                name,
                VariableProvenance.CURRENT_AUTHOR_INSTRUCTION,
                VariableSecurity.XML_REQUIRED,
            )
            for name in user_content_vars
        },
        **{
            name: VariableClassification(
                name,
                VariableProvenance.SYSTEM_GENERATED,
                VariableSecurity.SYSTEM_ONLY,
            )
            for name in system_vars
        },
        **{
            name: VariableClassification(
                name,
                VariableProvenance.FEATURE_DYNAMIC,
                VariableSecurity.SYSTEM_ONLY,
            )
            for name in feature_dynamic_vars
        },
    }
    return {**base, **_classification_overrides()}


def _classification_overrides() -> dict[str, VariableClassification]:
    """Variable-specific metadata where the legacy top-level bucket is too broad."""
    return {
        **{
            name: VariableClassification(
                name,
                VariableProvenance.CURATED_KB,
                VariableSecurity.XML_SECTION_REQUIRED,
            )
            for name in (
                "world_context",
                "kb_characters",
                "kb_locations",
                "kb_factions",
                "kb_relationships",
                "kb_entities",
                "kb_summary",
                "kb_context_entries",
            )
        },
        **{
            name: VariableClassification(
                name,
                VariableProvenance.LEARNED_MEMORY,
                VariableSecurity.LABEL_REQUIRED,
            )
            for name in ("user_preferences", "avoidance_patterns", "style_constraints")
        },
        **{
            name: VariableClassification(
                name,
                VariableProvenance.PROJECT_WRITING_PROFILE,
                security,
            )
            for name, security in (
                ("writing_language", VariableSecurity.SYSTEM_ONLY),
                ("genre", VariableSecurity.SYSTEM_ONLY),
                ("tone", VariableSecurity.SYSTEM_ONLY),
                ("style_profile", VariableSecurity.LABEL_REQUIRED),
            )
        },
        **{
            name: VariableClassification(
                name,
                VariableProvenance.SCENE_STORY_PLAN,
                security,
            )
            for name, security in (
                ("story_structure", VariableSecurity.SYSTEM_ONLY),
                ("timeline_position", VariableSecurity.SYSTEM_ONLY),
                ("chapter_outline", VariableSecurity.LABEL_REQUIRED),
            )
        },
        **{
            name: VariableClassification(
                name,
                VariableProvenance.GENERATED_SUGGESTION,
                VariableSecurity.GENERATED_LABEL_REQUIRED,
            )
            for name in ("kb_suggested", "candidate_pairs", "entity_events")
        },
    }
