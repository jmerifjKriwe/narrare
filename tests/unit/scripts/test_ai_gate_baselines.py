"""Tests for Review-03 ratcheted platform gates."""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_ROOT / "scripts"))

from scripts.architecture.baselines import compare_section  # noqa: E402
from scripts.check_exception_baseline import collect_exception_fingerprints  # noqa: E402
from scripts.check_frontend_file_size import collect_violations  # noqa: E402


def test_compare_section_allows_debt_to_decrease(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps({"warnings": ["legacy", "resolved"]}))

    comparison = compare_section({"legacy"}, "warnings", baseline_path)

    assert comparison.ok
    assert comparison.resolved_items == {"resolved"}


def test_compare_section_flags_new_debt(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps({"warnings": ["legacy"]}))

    comparison = compare_section({"legacy", "new"}, "warnings", baseline_path)

    assert not comparison.ok
    assert comparison.new_items == {"new"}


def test_frontend_file_size_uses_type_specific_limits(tmp_path: Path) -> None:
    web_dir = tmp_path / "web"
    page_dir = web_dir / "app" / "studio"
    page_dir.mkdir(parents=True)
    page = page_dir / "page.tsx"
    page.write_text("x\n" * 101)
    component = web_dir / "Component.tsx"
    component.write_text("x\n" * 201)

    violations = collect_violations(web_dir)

    assert {item.kind for item in violations} == {"page", "component"}
    assert {item.limit for item in violations} == {100, 200}


def test_exception_baseline_collects_pyproject_and_inline_fallbacks(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        textwrap.dedent(
            """
            [tool.narrare.architecture.exceptions]
            [[tool.narrare.architecture.exceptions.entries]]
            rule = "RULE-01b"
            file = "packages/core/example.py"
            reason = "ADR-approved adapter"
            """
        )
    )
    registry = tmp_path / "adoption-registry.yaml"
    registry.write_text(
        textwrap.dedent(
            """
            inline_fallbacks:
              - file: apps/api/example.py
                variable: FALLBACK
                migration_target: packages/core/prompts/example.md
            """
        )
    )

    fingerprints = collect_exception_fingerprints(pyproject, registry)

    assert "pyproject | RULE-01b | packages/core/example.py | ADR-approved adapter" in fingerprints
    assert (
        "inline_fallback | apps/api/example.py | FALLBACK | packages/core/prompts/example.md"
        in fingerprints
    )
