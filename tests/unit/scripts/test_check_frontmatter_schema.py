"""Tests for scripts/check_frontmatter_schema.py — ratcheted frontmatter schema gate.

Covers schema validation (required fields, unknown-field/typo detection, enum
values, semver), file discovery (system.md only), and the baseline ratchet gate
(main exit codes).

This checker addresses the root cause that ``parse_frontmatter()`` performs no
schema validation (CR-AUFG-04-03): a typo such as ``prompt_typ:`` is silently
accepted at runtime. The checker is WARNING-only with a clean-baseline ratchet.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.check_frontmatter_schema import (  # noqa: E402
    collect_frontmatter_schema_findings,
    validate_frontmatter_schema,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_system_md(bundled: Path, rel: str, frontmatter: str, body: str = "Body.\n") -> Path:
    """Write a system.md file with the given raw frontmatter block under bundled/."""
    target = bundled / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"---\n{frontmatter}\n---\n\n{body}", encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# Tests: validate_frontmatter_schema (pure logic)
# ---------------------------------------------------------------------------


class TestValidateSchema:
    """The pure validator maps a metadata dict to warning messages."""

    def test_valid_frontmatter_yields_no_warnings(self) -> None:
        metadata = {
            "prompt_type": "writing",
            "prompt_language": "en",
            "prompt_version": "1.0.0",
        }
        assert validate_frontmatter_schema(metadata) == []

    def test_missing_prompt_type_warns(self) -> None:
        warnings = validate_frontmatter_schema({"prompt_language": "en", "prompt_version": "1.0.0"})
        assert any("prompt_type" in w and "missing" in w for w in warnings)

    def test_missing_prompt_language_warns(self) -> None:
        warnings = validate_frontmatter_schema(
            {"prompt_type": "writing", "prompt_version": "1.0.0"}
        )
        assert any("prompt_language" in w and "missing" in w for w in warnings)

    def test_missing_prompt_version_warns(self) -> None:
        warnings = validate_frontmatter_schema({"prompt_type": "writing", "prompt_language": "en"})
        assert any("prompt_version" in w and "missing" in w for w in warnings)

    def test_unknown_field_typo_warns(self) -> None:
        # The canonical typo case: prompt_typ instead of prompt_type.
        warnings = validate_frontmatter_schema(
            {
                "prompt_typ": "writing",
                "prompt_language": "en",
                "prompt_version": "1.0.0",
            }
        )
        assert any("prompt_typ" in w and "unknown" in w for w in warnings)

    def test_unknown_extra_field_warns(self) -> None:
        warnings = validate_frontmatter_schema(
            {
                "prompt_type": "writing",
                "prompt_language": "en",
                "prompt_version": "1.0.0",
                "extra_categorization": "something",
            }
        )
        assert any("extra_categorization" in w and "unknown" in w for w in warnings)

    def test_invalid_prompt_type_value_warns(self) -> None:
        warnings = validate_frontmatter_schema(
            {"prompt_type": "fiction", "prompt_language": "en", "prompt_version": "1.0.0"}
        )
        assert any("invalid prompt_type" in w and "fiction" in w for w in warnings)

    def test_invalid_prompt_language_value_warns(self) -> None:
        warnings = validate_frontmatter_schema(
            {"prompt_type": "writing", "prompt_language": "es", "prompt_version": "1.0.0"}
        )
        assert any("invalid prompt_language" in w and "es" in w for w in warnings)

    def test_malformed_prompt_version_warns(self) -> None:
        warnings = validate_frontmatter_schema(
            {"prompt_type": "writing", "prompt_language": "en", "prompt_version": "1.0"}
        )
        assert any("prompt_version" in w and "1.0" in w for w in warnings)

    def test_typo_emits_both_missing_and_unknown(self) -> None:
        # prompt_typ typo: missing prompt_type AND unknown prompt_typ.
        warnings = validate_frontmatter_schema(
            {
                "prompt_typ": "writing",
                "prompt_language": "en",
                "prompt_version": "1.0.0",
            }
        )
        assert any("missing" in w and "prompt_type" in w for w in warnings)
        assert any("unknown" in w and "prompt_typ" in w for w in warnings)

    def test_empty_string_required_field_treated_as_missing(self) -> None:
        warnings = validate_frontmatter_schema(
            {"prompt_type": "", "prompt_language": "en", "prompt_version": "1.0.0"}
        )
        assert any("prompt_type" in w and "missing" in w for w in warnings)


# ---------------------------------------------------------------------------
# Tests: discovery (collect_frontmatter_schema_findings)
# ---------------------------------------------------------------------------


class TestCollectFindings:
    """The collector discovers system.md files and skips non-system files."""

    def test_no_findings_on_clean_system_md(self, tmp_path: Path) -> None:
        bundled = tmp_path / "packages" / "core" / "narrare_core" / "prompts" / "_bundled"
        _write_system_md(
            bundled,
            "writing/en/chat/system.md",
            'prompt_type: writing\nprompt_language: en\nprompt_version: "1.4.0"',
        )
        findings = collect_frontmatter_schema_findings(bundled, repo_root=tmp_path)
        assert findings == set()

    def test_detects_unknown_field_in_system_md(self, tmp_path: Path) -> None:
        bundled = tmp_path / "packages" / "core" / "narrare_core" / "prompts" / "_bundled"
        _write_system_md(
            bundled,
            "writing/en/chat/system.md",
            'prompt_typ: writing\nprompt_language: en\nprompt_version: "1.4.0"',
        )
        findings = collect_frontmatter_schema_findings(bundled, repo_root=tmp_path)
        assert any("prompt_typ" in f and "unknown" in f for f in findings)

    def test_skips_non_system_md_files(self, tmp_path: Path) -> None:
        """Tone/name-style .md files (with style_id, tone_id, etc.) are ignored."""
        bundled = tmp_path / "packages" / "core" / "narrare_core" / "prompts" / "_bundled"
        # A tones file — not system.md — with optional fields must NOT warn.
        tones = bundled / "writing" / "tones" / "quiet.md"
        tones.parent.mkdir(parents=True)
        tones.write_text(
            "---\nlanguage: en\nstyle_id: quiet\nstyle_name: Quiet\n"
            'tone_id: quiet\ntone_version: "1.0.0"\nversion: "1.0.0"\n---\n\nBody.\n',
            encoding="utf-8",
        )
        findings = collect_frontmatter_schema_findings(bundled, repo_root=tmp_path)
        assert findings == set()

    def test_fingerprint_uses_repo_relative_path(self, tmp_path: Path) -> None:
        bundled = tmp_path / "packages" / "core" / "narrare_core" / "prompts" / "_bundled"
        _write_system_md(
            bundled,
            "kb/en/extract/system.md",
            'prompt_type: kb\nprompt_language: en\nprompt_version: "x.y"',
        )
        findings = collect_frontmatter_schema_findings(bundled, repo_root=tmp_path)
        joined = " ".join(sorted(findings))
        assert "packages/core/narrare_core/prompts/_bundled/kb/en/extract/system.md" in joined


# ---------------------------------------------------------------------------
# Tests: baseline gate (main exit codes)
# ---------------------------------------------------------------------------


class TestMainGate:
    """The checker exits 0 on matching baseline, 1 on new findings."""

    @pytest.fixture
    def bundled(self, tmp_path: Path) -> Path:
        bundled = tmp_path / "packages" / "core" / "narrare_core" / "prompts" / "_bundled"
        bundled.mkdir(parents=True)
        return bundled

    def test_exits_zero_when_findings_match_baseline(
        self,
        tmp_path: Path,
        bundled: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_system_md(
            bundled,
            "writing/en/chat/system.md",
            'prompt_typ: writing\nprompt_language: en\nprompt_version: "1.4.0"',
        )
        baseline_path = tmp_path / "baseline.json"
        baseline_path.write_text(
            json.dumps(
                {
                    "frontmatter_schema_warnings": [
                        "packages/core/narrare_core/prompts/_bundled/writing/en/chat/system.md "
                        "| unknown frontmatter field 'prompt_typ' (possible typo)",
                        "packages/core/narrare_core/prompts/_bundled/writing/en/chat/system.md "
                        "| missing required frontmatter field 'prompt_type'",
                    ]
                }
            )
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "check_frontmatter_schema.py",
                "--baseline",
                str(baseline_path),
                "--bundled-dir",
                str(bundled),
                "--repo-root",
                str(tmp_path),
            ],
        )
        from scripts.check_frontmatter_schema import main

        assert main() == 0

    def test_exits_one_on_new_finding(
        self,
        tmp_path: Path,
        bundled: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_system_md(
            bundled,
            "writing/en/chat/system.md",
            'prompt_typ: writing\nprompt_language: en\nprompt_version: "1.4.0"',
        )
        baseline_path = tmp_path / "baseline.json"
        baseline_path.write_text(json.dumps({"frontmatter_schema_warnings": []}))
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "check_frontmatter_schema.py",
                "--baseline",
                str(baseline_path),
                "--bundled-dir",
                str(bundled),
                "--repo-root",
                str(tmp_path),
            ],
        )
        from scripts.check_frontmatter_schema import main

        assert main() == 1
        captured = capsys.readouterr()
        assert "NEW:" in captured.out
        assert "prompt_typ" in captured.out

    def test_exits_zero_on_clean_baseline(
        self,
        tmp_path: Path,
        bundled: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_system_md(
            bundled,
            "writing/en/chat/system.md",
            'prompt_type: writing\nprompt_language: en\nprompt_version: "1.4.0"',
        )
        baseline_path = tmp_path / "baseline.json"
        baseline_path.write_text(json.dumps({"frontmatter_schema_warnings": []}))
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "check_frontmatter_schema.py",
                "--baseline",
                str(baseline_path),
                "--bundled-dir",
                str(bundled),
                "--repo-root",
                str(tmp_path),
            ],
        )
        from scripts.check_frontmatter_schema import main

        assert main() == 0

    def test_reports_resolved_when_baseline_item_disappears(
        self,
        tmp_path: Path,
        bundled: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_system_md(
            bundled,
            "writing/en/chat/system.md",
            'prompt_type: writing\nprompt_language: en\nprompt_version: "1.4.0"',
        )
        baseline_path = tmp_path / "baseline.json"
        baseline_path.write_text(
            json.dumps(
                {
                    "frontmatter_schema_warnings": [
                        "packages/core/narrare_core/prompts/_bundled/writing/en/chat/system.md "
                        "| unknown frontmatter field 'old_typo' (possible typo)"
                    ]
                }
            )
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "check_frontmatter_schema.py",
                "--baseline",
                str(baseline_path),
                "--bundled-dir",
                str(bundled),
                "--repo-root",
                str(tmp_path),
            ],
        )
        from scripts.check_frontmatter_schema import main

        assert main() == 0
        captured = capsys.readouterr()
        assert "RESOLVED:" in captured.out
        assert "0 current" in captured.out
