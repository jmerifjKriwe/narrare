"""Tests for scripts/check_kg_consistency.py.

Validates the KG consistency checker with mock prompt files and registry data.

See: ADR-040 Decision 2.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_SCRIPTS = str(Path(__file__).resolve().parent.parent.parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import yaml  # noqa: E402
from check_kg_consistency import (  # noqa: E402
    KGConsistencyResult,
    KGMismatch,
    _get_mode_kg_vars,
    _is_kg_variable,
    _scan_prompt_variables,
    check_kg_consistency,
)

# ── Helpers ────────────────────────────────────────────────────────


def _make_registry_file(
    tmp_path: Path,
    features: dict[str, object] | None = None,
) -> Path:
    """Create a temporary adoption-registry.yaml."""
    registry: dict[str, object] = {
        "features": features
        or {
            "writing": {
                "modes": {"new_chapter": {}},
                "required_infrastructure": {},
                "context_variables": {
                    "must": ["user_preferences", "kb_characters"],
                    "should": ["kb_suggested"],
                },
            }
        }
    }
    p = tmp_path / "adoption-registry.yaml"
    p.write_text(yaml.dump(registry, default_flow_style=False), encoding="utf-8")
    return p


def _make_prompt_file(
    tmp_path: Path,
    category: str,
    mode: str,
    content: str,
) -> Path:
    """Create a mock prompt file in the _bundled directory structure."""
    prompts_dir = tmp_path / "_bundled"
    mode_dir = prompts_dir / category / "en" / mode
    mode_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = mode_dir / "system.md"
    prompt_file.write_text(content, encoding="utf-8")
    return prompts_dir


# ── _is_kg_variable ───────────────────────────────────────────────


class TestIsKgVariable:
    def test_kb_prefix(self) -> None:
        assert _is_kg_variable("kb_characters") is True
        assert _is_kg_variable("kb_locations") is True
        assert _is_kg_variable("kb_suggested") is True

    def test_character_prefix(self) -> None:
        assert _is_kg_variable("character_voice_profiles") is True

    def test_world_context(self) -> None:
        assert _is_kg_variable("world_context") is True

    def test_non_kg_variable(self) -> None:
        assert _is_kg_variable("user_preferences") is False
        assert _is_kg_variable("avoidance_patterns") is False
        assert _is_kg_variable("mode") is False


# ── _get_mode_kg_vars ─────────────────────────────────────────────


class TestGetModeKgVars:
    def test_extracts_kg_from_must_and_should(self) -> None:
        ctx: dict[str, object] = {
            "must": ["kb_characters", "user_preferences"],
            "should": ["kb_suggested", "character_voice_profiles"],
        }
        kg_vars = _get_mode_kg_vars({}, ctx)
        assert "kb_characters" in kg_vars
        assert "kb_suggested" in kg_vars
        assert "character_voice_profiles" in kg_vars
        assert "user_preferences" not in kg_vars

    def test_mode_overrides(self) -> None:
        overrides: dict[str, object] = {
            "context_variables": {
                "must": ["kb_characters"],
                "should": [],
            }
        }
        ctx: dict[str, object] = {
            "must": ["kb_characters", "kb_locations"],
            "should": ["kb_suggested"],
        }
        kg_vars = _get_mode_kg_vars(overrides, ctx)
        assert "kb_characters" in kg_vars
        # Overrides replace category-level must/should.
        assert "kb_locations" not in kg_vars

    def test_empty(self) -> None:
        kg_vars = _get_mode_kg_vars({}, {})
        assert kg_vars == set()


# ── _scan_prompt_variables ────────────────────────────────────────


class TestScanPromptVariables:
    def test_finds_kg_variables(self, tmp_path: Path) -> None:
        prompts_dir = _make_prompt_file(
            tmp_path,
            "writing",
            "new_chapter",
            "Use {{kb_characters}} and {{kb_locations}} for context.",
        )
        vars_found = _scan_prompt_variables(prompts_dir, "writing", "new_chapter")
        assert "kb_characters" in vars_found
        assert "kb_locations" in vars_found

    def test_excludes_non_kg(self, tmp_path: Path) -> None:
        prompts_dir = _make_prompt_file(
            tmp_path,
            "writing",
            "new_chapter",
            "Use {{user_preferences}} and {{kb_characters}}.",
        )
        vars_found = _scan_prompt_variables(prompts_dir, "writing", "new_chapter")
        assert "kb_characters" in vars_found
        assert "user_preferences" not in vars_found

    def test_missing_mode_dir(self, tmp_path: Path) -> None:
        prompts_dir = tmp_path / "_bundled"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        vars_found = _scan_prompt_variables(prompts_dir, "writing", "nonexistent")
        assert vars_found == set()


# ── KGConsistencyResult serialization ──────────────────────────────


class TestKGConsistencyResult:
    def test_to_json(self) -> None:
        result = KGConsistencyResult(
            checked_modes=5,
            critical_count=0,
            warning_count=1,
            ok=True,
            mismatches=[
                KGMismatch(
                    category="writing",
                    mode="new_chapter",
                    variable="kb_suggested",
                    mismatch_type="missing_in_registry",
                    severity="warning",
                    message="test",
                )
            ],
        )
        data = json.loads(result.to_json())
        assert data["checked_modes"] == 5
        assert data["ok"] is True
        assert len(data["mismatches"]) == 1

    def test_to_text_no_mismatches(self) -> None:
        result = KGConsistencyResult(checked_modes=3, ok=True)
        text = result.to_text()
        assert "3 modes checked" in text
        assert "No mismatches" in text

    def test_to_text_with_mismatches(self) -> None:
        result = KGConsistencyResult(
            checked_modes=3,
            ok=False,
            critical_count=1,
            warning_count=1,
            mismatches=[
                KGMismatch(
                    category="writing",
                    mode="new_chapter",
                    variable="kb_characters",
                    mismatch_type="missing_in_prompt",
                    severity="critical",
                    message="Registry requires 'kb_characters' but prompt doesn't use it",
                ),
            ],
        )
        text = result.to_text()
        assert "1 critical" in text
        assert "1 warning" in text


# ── check_kg_consistency integration ──────────────────────────────


class TestCheckKgConsistency:
    def test_perfect_match(self, tmp_path: Path) -> None:
        """All required KG vars are in the prompt."""
        registry_path = _make_registry_file(tmp_path)
        prompts_dir = _make_prompt_file(
            tmp_path,
            "writing",
            "new_chapter",
            "Use {{kb_characters}} and {{kb_suggested}} for context.",
        )
        result = check_kg_consistency(registry_path, prompts_dir)
        assert result.ok
        assert result.checked_modes >= 1
        # kb_characters is in prompt and registry → no mismatch for it.
        kb_char_mismatches = [m for m in result.mismatches if m.variable == "kb_characters"]
        assert len(kb_char_mismatches) == 0

    def test_missing_in_prompt(self, tmp_path: Path) -> None:
        """Registry requires kb_characters but prompt doesn't use it."""
        registry_path = _make_registry_file(tmp_path)
        prompts_dir = _make_prompt_file(
            tmp_path,
            "writing",
            "new_chapter",
            "Use {{user_preferences}} for settings.",
        )
        result = check_kg_consistency(registry_path, prompts_dir)
        assert not result.ok
        missing = [m for m in result.mismatches if m.variable == "kb_characters"]
        assert len(missing) >= 1
        assert missing[0].mismatch_type == "missing_in_prompt"
        assert missing[0].severity == "critical"

    def test_undeclared_in_registry(self, tmp_path: Path) -> None:
        """Prompt uses a KG variable not declared in the registry."""
        registry_path = _make_registry_file(
            tmp_path,
            features={
                "writing": {
                    "modes": {"new_chapter": {}},
                    "required_infrastructure": {},
                    "context_variables": {
                        "must": ["user_preferences"],
                        "should": [],
                    },
                }
            },
        )
        prompts_dir = _make_prompt_file(
            tmp_path,
            "writing",
            "new_chapter",
            "Use {{kb_characters}} for context.",
        )
        result = check_kg_consistency(registry_path, prompts_dir)
        undeclared = [
            m
            for m in result.mismatches
            if m.variable == "kb_characters" and m.mismatch_type == "missing_in_registry"
        ]
        assert len(undeclared) >= 1
        assert undeclared[0].severity == "warning"

    def test_no_prompts_dir(self, tmp_path: Path) -> None:
        """Missing prompt directory still works (no prompt files to scan)."""
        registry_path = _make_registry_file(tmp_path)
        prompts_dir = tmp_path / "_bundled"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        result = check_kg_consistency(registry_path, prompts_dir)
        # All registry KG vars are missing from (nonexistent) prompts.
        assert not result.ok

    def test_mode_with_overrides(self, tmp_path: Path) -> None:
        """Mode-level overrides affect which KG vars are required."""
        registry_path = _make_registry_file(
            tmp_path,
            features={
                "writing": {
                    "modes": {
                        "inline_suggest": {
                            "overrides": {
                                "context_variables": {
                                    "should": ["kb_suggested"],
                                },
                            },
                        },
                    },
                    "required_infrastructure": {},
                    "context_variables": {
                        "must": ["user_preferences", "kb_characters"],
                        "should": [],
                    },
                }
            },
        )
        prompts_dir = _make_prompt_file(
            tmp_path,
            "writing",
            "inline_suggest",
            "Prompt with {{kb_suggested}}.",
        )
        result = check_kg_consistency(registry_path, prompts_dir)
        # kb_suggested is in prompt and in override should → no mismatch for it.
        suggested = [m for m in result.mismatches if m.variable == "kb_suggested"]
        assert len(suggested) == 0

    def test_list_mode_format(self, tmp_path: Path) -> None:
        """Legacy list format for modes."""
        registry_path = _make_registry_file(
            tmp_path,
            features={
                "writing": {
                    "modes": ["new_chapter"],
                    "required_infrastructure": {},
                    "context_variables": {
                        "must": ["kb_characters"],
                        "should": [],
                    },
                }
            },
        )
        prompts_dir = _make_prompt_file(
            tmp_path,
            "writing",
            "new_chapter",
            "Use {{kb_characters}} for context.",
        )
        result = check_kg_consistency(registry_path, prompts_dir)
        kb_char = [m for m in result.mismatches if m.variable == "kb_characters"]
        assert len(kb_char) == 0
