"""Tests for scripts/check_registry_drift.py — schema validation & shared fixtures.

Validates schema validation (TestSchemaValidation) and provides shared
fixtures for mode-alignment drift tests.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

# ── Public API for sibling test files ─────────────────────────────────
__all__ = ["_make_prompt_file", "_write_env"]

# Project root for `scripts.*` imports.
_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scripts.check_registry_drift import (  # noqa: E402
    validate_registry_schema,
)

# ── Shared Fixtures & Helpers ────────────────────────────────────────────

_MINIMAL_SCHEMA: dict[str, object] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["version", "features"],
    "additionalProperties": False,
    "properties": {
        "version": {"type": "string", "const": "2.0.0"},
        "features": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "required": ["modes", "required_infrastructure", "context_variables"],
                "properties": {
                    "modes": {
                        "oneOf": [
                            {
                                "type": "object",
                                "additionalProperties": {
                                    "type": "object",
                                    "required": ["requires_runtime_evidence"],
                                    "properties": {
                                        "requires_runtime_evidence": {
                                            "type": "boolean",
                                        },
                                    },
                                    "additionalProperties": False,
                                },
                            },
                            {"type": "array", "maxItems": 0},
                        ],
                    },
                    "required_infrastructure": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "string",
                            "enum": ["required", "partial", "optional"],
                        },
                    },
                    "context_variables": {
                        "type": "object",
                        "required": ["must", "should"],
                        "properties": {
                            "must": {"type": "array", "items": {"type": "string"}},
                            "should": {"type": "array", "items": {"type": "string"}},
                        },
                        "additionalProperties": False,
                    },
                },
                "additionalProperties": False,
            },
        },
    },
}


def _make_registry(
    *,
    features: dict[str, object] | None = None,
    version: str = "2.0.0",
) -> dict[str, object]:
    """Build a minimal valid registry."""
    if features is None:
        features = {
            "writing": {
                "modes": {
                    "new_chapter": {"requires_runtime_evidence": True},
                },
                "required_infrastructure": {"prompt_composer": "required"},
                "context_variables": {"must": ["user_preferences"], "should": []},
            },
        }
    return {"version": version, "features": features}


def _write_env(
    tmp_path: Path,
    registry: dict[str, object],
) -> tuple[Path, Path]:
    """Write registry YAML + schema JSON. Returns (reg_path, prompts_dir)."""
    reg_path = tmp_path / "adoption-registry.yaml"
    reg_path.write_text(
        yaml.dump(registry, default_flow_style=False),
        encoding="utf-8",
    )
    schema_path = tmp_path / "adoption-registry.schema.json"
    schema_path.write_text(json.dumps(_MINIMAL_SCHEMA), encoding="utf-8")
    return reg_path, tmp_path / "_bundled"


def _write_schema_only(tmp_path: Path) -> Path:
    """Write schema JSON alone (for validate_registry_schema tests)."""
    schema_path = tmp_path / "adoption-registry.schema.json"
    schema_path.write_text(json.dumps(_MINIMAL_SCHEMA), encoding="utf-8")
    return schema_path


def _make_prompt_file(
    prompts_dir: Path,
    category: str,
    mode: str,
    locale: str = "en",
) -> Path:
    """Create a minimal prompt file in the mock filesystem."""
    target = prompts_dir / category / locale / mode if mode else prompts_dir / category / locale
    target.mkdir(parents=True, exist_ok=True)
    prompt_file = target / "system.md"
    prompt_file.write_text(f"# {category}/{mode} prompt\n", encoding="utf-8")
    return prompt_file


# ── TestSchemaValidation ───────────────────────────────────────────────


class TestSchemaValidation:
    """Valid registry passes schema, invalid fails."""

    def test_valid_registry_passes(self, tmp_path: Path) -> None:
        registry = _make_registry()
        findings = validate_registry_schema(registry, _write_schema_only(tmp_path))
        assert findings == []

    def test_invalid_version_fails(self, tmp_path: Path) -> None:
        registry = _make_registry(version="1.0.0")
        findings = validate_registry_schema(registry, _write_schema_only(tmp_path))
        assert len(findings) == 1
        assert findings[0].severity == "critical"
        assert "version" in findings[0].message.lower() or "2.0.0" in findings[0].message

    def test_missing_features_fails(self, tmp_path: Path) -> None:
        registry: dict[str, object] = {"version": "2.0.0"}
        findings = validate_registry_schema(registry, _write_schema_only(tmp_path))
        assert len(findings) == 1
        assert findings[0].severity == "critical"

    def test_extra_top_level_key_fails(self, tmp_path: Path) -> None:
        registry = _make_registry()
        registry["unknown_key"] = "not allowed"
        findings = validate_registry_schema(registry, _write_schema_only(tmp_path))
        assert len(findings) == 1
        assert findings[0].severity == "critical"
