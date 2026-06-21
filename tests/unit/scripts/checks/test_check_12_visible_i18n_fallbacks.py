"""Tests for Check 12 — Visible i18n fallback string scanner.

Ensures no visible English fallback strings are reintroduced in KB and
editor Studio components (CR-AUFG-07-14).
"""

from __future__ import annotations

from pathlib import Path

from _ai_interaction_checks.check_12_visible_i18n_fallbacks import (
    GATE,
    _find_visible_i18n_fallbacks_in_source,
    check_visible_i18n_fallbacks,
)

# ---------------------------------------------------------------------------
# Gate name
# ---------------------------------------------------------------------------


def test_gate_name_matches_convention() -> None:
    assert GATE == "check_12_visible_i18n_fallbacks"


# ---------------------------------------------------------------------------
# _find_visible_i18n_fallbacks_in_source — pattern detection
# ---------------------------------------------------------------------------


def test_detects_t_call_with_or_fallback() -> None:
    """``t("kb.selectAll") || "Select all"`` is a violation (pattern 1)."""
    source = 'const label = t("kb.selectAll") || "Select all";'
    findings = _find_visible_i18n_fallbacks_in_source(source, Path("Component.tsx"))

    assert len(findings) == 1
    assert findings[0].line == 1
    assert "Select all" in findings[0].snippet


def test_detects_t_call_with_nullish_fallback() -> None:
    """``(t("worldbuilding.error")) ?? "Analysis failed"`` is a violation."""
    source = 'const msg = (t("worldbuilding.error")) ?? "Analysis failed";'
    findings = _find_visible_i18n_fallbacks_in_source(source, Path("Component.tsx"))

    assert len(findings) == 1
    assert "Analysis failed" in findings[0].snippet


def test_detects_capitalized_nullish_fallback_without_t_call() -> None:
    """``placeholder ?? "Tags"`` is a violation even without a ``t()`` call."""
    source = '<input aria-label={placeholder ?? "Tags"} />'
    findings = _find_visible_i18n_fallbacks_in_source(source, Path("Component.tsx"))

    assert len(findings) == 1
    assert "Tags" in findings[0].snippet


def test_detects_capitalized_or_fallback_without_t_call() -> None:
    """``error?.message || "Failed to save"`` is a violation."""
    source = 'const msg = error?.message || "Failed to save";'
    findings = _find_visible_i18n_fallbacks_in_source(source, Path("Component.tsx"))

    assert len(findings) == 1
    assert "Failed to save" in findings[0].snippet


def test_detects_single_quote_and_backtick_literals() -> None:
    """Single-quoted and backtick literals are also detected."""
    source = "const a = t('key') || 'Fallback';\nconst b = value ?? `Default`;"
    findings = _find_visible_i18n_fallbacks_in_source(source, Path("Component.tsx"))

    assert len(findings) == 2
    assert findings[0].line == 1
    assert findings[1].line == 2


def test_clean_source_produces_no_findings() -> None:
    """Source without fallbacks produces zero findings."""
    source = (
        'const label = t("kb.selectAll");\n'
        'const msg = t("worldbuilding.error");\n'
        "const count = items.length || 0;\n"
        "const enabled = flag ?? false;\n"
        'const className = cls ?? "default-class";\n'
    )
    findings = _find_visible_i18n_fallbacks_in_source(source, Path("Component.tsx"))

    assert findings == []


def test_ignores_lowercase_string_fallback_without_t_call() -> None:
    """Lowercase string fallbacks without ``t()`` are NOT violations.

    These are typically CSS class names or data attributes, not visible text.
    Only lowercase fallbacks after a ``t()`` call are violations.
    """
    source = 'const cls = primary ?? "secondary";'
    findings = _find_visible_i18n_fallbacks_in_source(source, Path("Component.tsx"))

    assert findings == []


def test_ignores_non_string_fallbacks() -> None:
    """``|| undefined``, ``?? false``, ``|| 0`` are NOT violations."""
    source = (
        "const a = value || undefined;\n"
        "const b = value ?? false;\n"
        "const c = value || 0;\n"
        "const d = value ?? null;\n"
    )
    findings = _find_visible_i18n_fallbacks_in_source(source, Path("Component.tsx"))

    assert findings == []


def test_reports_correct_line_number_in_multiline_source() -> None:
    """Line number reflects the actual line in the source text."""
    source = (
        'const a = "first";\n'
        'const b = "second";\n'
        'const label = t("key") || "Fallback";\n'
        'const c = "fourth";\n'
    )
    findings = _find_visible_i18n_fallbacks_in_source(source, Path("Component.tsx"))

    assert len(findings) == 1
    assert findings[0].line == 3


def test_finding_contains_remediation_guidance() -> None:
    """Each finding provides actionable remediation text."""
    source = 'const label = t("key") || "Fallback";'
    findings = _find_visible_i18n_fallbacks_in_source(source, Path("Component.tsx"))

    assert len(findings) == 1
    assert len(findings[0].remediation) > 10


def test_deduplicates_findings_on_same_line() -> None:
    """A line matching multiple patterns produces one finding, not duplicates."""
    source = 'const a = t("key") || "Fallback";'
    findings = _find_visible_i18n_fallbacks_in_source(source, Path("Component.tsx"))

    # Both patterns match (t() fallback AND capital string fallback),
    # but only one finding should be reported per line.
    assert len(findings) == 1


# ---------------------------------------------------------------------------
# check_visible_i18n_fallbacks — integration
# ---------------------------------------------------------------------------


def _write_allowlist(path: Path, entries: list[dict[str, str]] | None = None) -> None:
    """Write a minimal allowlist YAML file."""
    import yaml

    path.write_text(yaml.dump({"entries": entries or []}), encoding="utf-8")


def _make_tree(root: Path) -> None:
    """Create the minimal studio/kb and studio/editor directories."""
    (root / "packages" / "web" / "components" / "studio" / "kb").mkdir(parents=True)
    (root / "packages" / "web" / "components" / "studio" / "editor").mkdir(parents=True)


def test_check_reports_production_kb_violation(tmp_path: Path) -> None:
    """A production KB file with a fallback is reported with path/line/snippet."""
    _make_tree(tmp_path)
    component = tmp_path / "packages" / "web" / "components" / "studio" / "kb" / "Component.tsx"
    component.write_text(
        "export function Component() {\n"
        '  return <span>{t("kb.selectAll") || "Select all"}</span>;\n'
        "}\n",
        encoding="utf-8",
    )
    allowlist = tmp_path / "allowlist.yaml"
    _write_allowlist(allowlist)

    _, violations = check_visible_i18n_fallbacks(root=tmp_path, allowlist_path=allowlist)

    assert len(violations) == 1
    violation = violations[0]
    assert "kb/Component.tsx" in violation
    assert ":2:" in violation  # line number
    assert "Select all" in violation


def test_check_reports_production_editor_violation(tmp_path: Path) -> None:
    """A production editor file with a fallback is also reported."""
    _make_tree(tmp_path)
    component = tmp_path / "packages" / "web" / "components" / "studio" / "editor" / "Editor.tsx"
    component.write_text(
        'const hint = options.text ?? "Default Hint";\n',
        encoding="utf-8",
    )
    allowlist = tmp_path / "allowlist.yaml"
    _write_allowlist(allowlist)

    _, violations = check_visible_i18n_fallbacks(root=tmp_path, allowlist_path=allowlist)

    assert len(violations) == 1
    assert "editor/Editor.tsx" in violations[0]


def test_check_skips_test_files_with_test_suffix(tmp_path: Path) -> None:
    """``*.test.tsx`` files are not scanned."""
    _make_tree(tmp_path)
    test_file = (
        tmp_path / "packages" / "web" / "components" / "studio" / "kb" / "Component.test.tsx"
    )
    test_file.write_text('const label = t("key") || "Fallback";\n', encoding="utf-8")
    allowlist = tmp_path / "allowlist.yaml"
    _write_allowlist(allowlist)

    passes, violations = check_visible_i18n_fallbacks(root=tmp_path, allowlist_path=allowlist)

    assert violations == []
    assert any("No visible i18n fallback" in p for p in passes)


def test_check_skips_spec_files(tmp_path: Path) -> None:
    """``*.spec.*`` files are not scanned."""
    _make_tree(tmp_path)
    spec_file = (
        tmp_path / "packages" / "web" / "components" / "studio" / "kb" / "Component.spec.tsx"
    )
    spec_file.write_text('const label = t("key") || "Fallback";\n', encoding="utf-8")
    allowlist = tmp_path / "allowlist.yaml"
    _write_allowlist(allowlist)

    _, violations = check_visible_i18n_fallbacks(root=tmp_path, allowlist_path=allowlist)

    assert violations == []


def test_check_skips_tests_directory(tmp_path: Path) -> None:
    """Files inside ``__tests__/`` directories are not scanned."""
    _make_tree(tmp_path)
    tests_dir = tmp_path / "packages" / "web" / "components" / "studio" / "kb" / "__tests__"
    tests_dir.mkdir()
    (tests_dir / "Helper.tsx").write_text(
        'const label = t("key") || "Fallback";\n', encoding="utf-8"
    )
    allowlist = tmp_path / "allowlist.yaml"
    _write_allowlist(allowlist)

    _, violations = check_visible_i18n_fallbacks(root=tmp_path, allowlist_path=allowlist)

    assert violations == []


def test_check_passes_on_clean_tree(tmp_path: Path) -> None:
    """A tree with no violations returns passes and no violations."""
    _make_tree(tmp_path)
    component = tmp_path / "packages" / "web" / "components" / "studio" / "kb" / "Clean.tsx"
    component.write_text(
        'export function Clean() {\n  return <span>{t("kb.title")}</span>;\n}\n',
        encoding="utf-8",
    )
    allowlist = tmp_path / "allowlist.yaml"
    _write_allowlist(allowlist)

    passes, violations = check_visible_i18n_fallbacks(root=tmp_path, allowlist_path=allowlist)

    assert violations == []
    assert any("No visible i18n fallback" in p for p in passes)


def test_check_handles_missing_scan_directories(tmp_path: Path) -> None:
    """Missing scan directories do not cause errors."""
    allowlist = tmp_path / "allowlist.yaml"
    _write_allowlist(allowlist)

    _, violations = check_visible_i18n_fallbacks(root=tmp_path, allowlist_path=allowlist)

    assert violations == []


def test_allowlist_suppresses_matching_finding(tmp_path: Path) -> None:
    """An allowlist entry with matching path+regex suppresses a finding."""
    _make_tree(tmp_path)
    component = tmp_path / "packages" / "web" / "components" / "studio" / "kb" / "Component.tsx"
    component.write_text('const label = t("key") || "Fallback";\n', encoding="utf-8")
    allowlist = tmp_path / "allowlist.yaml"
    _write_allowlist(
        allowlist,
        entries=[
            {
                "path": "packages/web/components/studio/kb/Component.tsx",
                "line_regex": "Fallback",
                "owner": "test",
                "reason": "Non-visible default for testing",
                "review_trigger": "2026-12-01",
            }
        ],
    )

    _, violations = check_visible_i18n_fallbacks(root=tmp_path, allowlist_path=allowlist)

    assert violations == []


def test_allowlist_does_not_suppress_non_matching_regex(tmp_path: Path) -> None:
    """An allowlist entry whose regex does not match does not suppress."""
    _make_tree(tmp_path)
    component = tmp_path / "packages" / "web" / "components" / "studio" / "kb" / "Component.tsx"
    component.write_text('const label = t("key") || "Fallback";\n', encoding="utf-8")
    allowlist = tmp_path / "allowlist.yaml"
    _write_allowlist(
        allowlist,
        entries=[
            {
                "path": "packages/web/components/studio/kb/Component.tsx",
                "line_regex": "DoesNotExist",
                "owner": "test",
                "reason": "test",
                "review_trigger": "2026-12-01",
            }
        ],
    )

    _, violations = check_visible_i18n_fallbacks(root=tmp_path, allowlist_path=allowlist)

    assert len(violations) == 1


def test_missing_allowlist_file_treated_as_empty(tmp_path: Path) -> None:
    """A missing allowlist file is treated as an empty allowlist."""
    _make_tree(tmp_path)
    component = tmp_path / "packages" / "web" / "components" / "studio" / "kb" / "Component.tsx"
    component.write_text('const label = t("key") || "Fallback";\n', encoding="utf-8")

    allowlist = tmp_path / "nonexistent.yaml"

    _, violations = check_visible_i18n_fallbacks(root=tmp_path, allowlist_path=allowlist)

    assert len(violations) == 1


def test_check_scans_both_ts_and_tsx(tmp_path: Path) -> None:
    """Both ``.ts`` and ``.tsx`` files are scanned."""
    _make_tree(tmp_path)
    (tmp_path / "packages" / "web" / "components" / "studio" / "kb" / "Module.ts").write_text(
        'export const label = t("key") || "Fallback";\n', encoding="utf-8"
    )
    (tmp_path / "packages" / "web" / "components" / "studio" / "kb" / "Component.tsx").write_text(
        'export const label = t("key") || "Fallback";\n', encoding="utf-8"
    )
    allowlist = tmp_path / "allowlist.yaml"
    _write_allowlist(allowlist)

    _, violations = check_visible_i18n_fallbacks(root=tmp_path, allowlist_path=allowlist)

    assert len(violations) == 2
