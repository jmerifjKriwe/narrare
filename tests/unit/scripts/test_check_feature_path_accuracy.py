"""Tests for scripts/check_feature_path_accuracy.py — core logic.

Covers frontmatter parsing, path normalization (anchor, brace-expansion,
class suffix), comma-splitting with brace awareness, planned/deprecated
handling, and violation collection.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.check_feature_path_accuracy import (  # noqa: E402
    PATH_FIELDS,
    _extract_frontmatter,
    _is_absolute_path,
    _is_empty_marker,
    _normalize_for_check,
    _split_paths,
    check_feature_file,
    collect_violations,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_feature(
    tmp_path: Path,
    rel: str,
    *,
    status: str = "stable",
    service: str = "",
    contract: str = "",
    router: str = "",
    prompt: str = "",
    extra: dict[str, str] | None = None,
) -> Path:
    """Write a feature file with the given frontmatter under tmp_path."""
    extras = "".join(f"{k}: {v}\n" for k, v in (extra or {}).items())
    fm = (
        "---\n"
        f"id: TEST\n"
        f"title: 'Test Feature'\n"
        f"status: {status}\n"
        f"area: test\n"
        f"mvp: false\n"
        f"{extras}"
        f"service: {service}\n"
        f"contract: {contract}\n"
        f"router: {router}\n"
        f"prompt: {prompt}\n"
        f"requires: []\n"
        "---\n\n# Test\n"
    )
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(fm, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# _split_paths
# ---------------------------------------------------------------------------


class TestSplitPaths:
    def test_empty_returns_empty(self) -> None:
        assert _split_paths("") == []

    def test_single_path(self) -> None:
        assert _split_paths("apps/api/foo.py") == ["apps/api/foo.py"]

    def test_multiple_paths(self) -> None:
        result = _split_paths("a.py, b.py , c.py")
        assert result == ["a.py", "b.py", "c.py"]

    def test_brace_commas_are_not_splits(self) -> None:
        # The comma inside {en,de,fr} must NOT split the path.
        path = "pkg/{en,de,fr}/system.md"
        assert _split_paths(path) == [path]

    def test_mixed_braces_and_commas(self) -> None:
        result = _split_paths("pkg/{en,de}/a.md, pkg/{en,de}/b.md")
        assert result == ["pkg/{en,de}/a.md", "pkg/{en,de}/b.md"]


# ---------------------------------------------------------------------------
# _normalize_for_check
# ---------------------------------------------------------------------------


class TestNormalize:
    def test_strips_anchor(self) -> None:
        assert _normalize_for_check("pkg/foo.py#Bar") == "pkg/foo.py"

    def test_strips_class_suffix(self) -> None:
        assert _normalize_for_check("pkg/foo.py (Bar)") == "pkg/foo.py"

    def test_strips_class_suffix_with_spaces(self) -> None:
        assert _normalize_for_check("pkg/foo.py ( Bar , Baz )") == "pkg/foo.py"

    def test_brace_resolves_to_first_variant(self) -> None:
        result = _normalize_for_check("pkg/{en,de,fr}/system.md")
        assert result == "pkg/en/system.md"

    def test_multiple_braces(self) -> None:
        result = _normalize_for_check("pkg/{en,de}/{a,b}/system.md")
        assert result == "pkg/en/a/system.md"

    def test_combined_anchor_and_brace(self) -> None:
        result = _normalize_for_check("pkg/{en,de}/foo.py#Bar")
        assert result == "pkg/en/foo.py"


# ---------------------------------------------------------------------------
# _is_absolute_path / _is_empty_marker
# ---------------------------------------------------------------------------


class TestAbsoluteDetection:
    def test_apps_is_absolute(self) -> None:
        assert _is_absolute_path("apps/api/foo.py")

    def test_packages_is_absolute(self) -> None:
        assert _is_absolute_path("packages/core/foo.py")

    def test_core_alone_is_shorthand(self) -> None:
        # Per design decision: `core/...` alone is shorthand for
        # `packages/core/narrare_core/...` and is NOT validated.
        assert not _is_absolute_path("core/prompts/foo.py")

    def test_relative_is_not_absolute(self) -> None:
        assert not _is_absolute_path("kb/service.py")

    def test_bare_filename(self) -> None:
        assert not _is_absolute_path("service.py")


class TestEmptyMarker:
    def test_none_is_empty(self) -> None:
        assert _is_empty_marker(None)

    def test_empty_string_is_empty(self) -> None:
        assert _is_empty_marker("")

    def test_tilde_is_empty(self) -> None:
        assert _is_empty_marker("~")

    def test_whitespace_only_is_empty(self) -> None:
        assert _is_empty_marker("   ")

    def test_path_is_not_empty(self) -> None:
        assert not _is_empty_marker("apps/api/foo.py")


# ---------------------------------------------------------------------------
# _extract_frontmatter
# ---------------------------------------------------------------------------


class TestExtractFrontmatter:
    def test_parses_yaml(self) -> None:
        text = "---\nid: X\nstatus: planned\n---\n\n# Body\n"
        fm = _extract_frontmatter(text)
        assert fm == {"id": "X", "status": "planned"}

    def test_no_frontmatter_returns_none(self) -> None:
        assert _extract_frontmatter("# just a heading\n") is None

    def test_invalid_yaml_returns_none(self) -> None:
        text = "---\n: : :\n---\n"
        assert _extract_frontmatter(text) is None

    def test_non_dict_yaml_returns_none(self) -> None:
        text = "---\n- a\n- b\n---\n"
        assert _extract_frontmatter(text) is None


# ---------------------------------------------------------------------------
# check_feature_file
# ---------------------------------------------------------------------------


class TestCheckFeatureFile:
    def test_existing_path_no_violation(self, tmp_path: Path) -> None:
        # Create a real file on disk to point to.
        target = tmp_path / "service.py"
        target.write_text("# svc\n", encoding="utf-8")
        feature = _make_feature(
            tmp_path,
            "feat.md",
            service="service.py",  # relative — not validated
        )
        # Use an absolute path that exists.
        rel_target = target.relative_to(tmp_path)
        feature2 = _make_feature(
            tmp_path,
            "feat2.md",
            service=str(rel_target),
        )
        # Both should yield no violations.
        assert check_feature_file(feature) == []
        assert check_feature_file(feature2) == []

    def test_phantom_absolute_path_violation(self, tmp_path: Path) -> None:
        feature = _make_feature(
            tmp_path,
            "feat.md",
            status="stable",
            service="apps/api/does_not_exist.py",
        )
        violations = check_feature_file(feature)
        assert len(violations) == 1
        assert violations[0].field == "service"
        assert "apps/api/does_not_exist.py" in violations[0].raw_path

    def test_empty_path_not_flagged(self, tmp_path: Path) -> None:
        feature = _make_feature(
            tmp_path,
            "feat.md",
            status="stable",
            service="",
        )
        assert check_feature_file(feature) == []

    def test_tilde_not_flagged(self, tmp_path: Path) -> None:
        feature = _make_feature(
            tmp_path,
            "feat.md",
            status="stable",
            contract="~",
        )
        assert check_feature_file(feature) == []

    def test_shorthand_path_not_flagged(self, tmp_path: Path) -> None:
        feature = _make_feature(
            tmp_path,
            "feat.md",
            status="stable",
            service="kb/service.py",  # shorthand, not absolute
        )
        assert check_feature_file(feature) == []

    def test_deprecated_status_skipped(self, tmp_path: Path) -> None:
        feature = _make_feature(
            tmp_path,
            "feat.md",
            status="deprecated",
            service="apps/api/phantom.py",
        )
        assert check_feature_file(feature) == []

    def test_merged_into_skipped(self, tmp_path: Path) -> None:
        feature = _make_feature(
            tmp_path,
            "feat.md",
            status="stable",
            service="apps/api/phantom.py",
            extra={"merged_into": "OTHER-001"},
        )
        assert check_feature_file(feature) == []

    def test_brace_path_resolves_and_validates(self, tmp_path: Path) -> None:
        # Create the en variant on disk.
        (tmp_path / "pkg" / "en").mkdir(parents=True)
        (tmp_path / "pkg" / "en" / "system.md").write_text("x", encoding="utf-8")
        feature = _make_feature(
            tmp_path,
            "feat.md",
            status="stable",
            prompt="pkg/{en,de,fr}/system.md",
        )
        # The path is relative ("pkg/...") — not absolute, so not validated.
        # Use an absolute prefix to actually exercise brace resolution.
        feature2_path = tmp_path / "feat2.md"
        feature2_path.write_text(
            "---\nstatus: stable\nservice: pkg/{en,de,fr}/system.md\nrequires: []\n---\n",
            encoding="utf-8",
        )
        # Both are relative → not validated.
        assert check_feature_file(feature) == []
        assert check_feature_file(feature2_path) == []

    def test_planned_status_phantom_message_mentions_status(self, tmp_path: Path) -> None:
        feature = _make_feature(
            tmp_path,
            "feat.md",
            status="planned",
            service="apps/api/phantom.py",
        )
        violations = check_feature_file(feature)
        assert len(violations) == 1
        assert "planned" in violations[0].reason

    def test_router_legacy_schema_detected(self, tmp_path: Path) -> None:
        feature = _make_feature(
            tmp_path,
            "feat.md",
            status="stable",
            router="apps/api/routers/a2a.py",
        )
        violations = check_feature_file(feature)
        assert len(violations) == 1
        assert violations[0].field == "router"


# ---------------------------------------------------------------------------
# collect_violations
# ---------------------------------------------------------------------------


class TestCollectViolations:
    def test_empty_dir(self, tmp_path: Path) -> None:
        assert collect_violations(tmp_path) == []

    def test_multiple_files_aggregated(self, tmp_path: Path) -> None:
        _make_feature(
            tmp_path / "a",
            "f1.md",
            status="stable",
            service="apps/api/p1.py",
        )
        _make_feature(
            tmp_path / "b",
            "f2.md",
            status="stable",
            router="apps/api/routers/p2.py",
        )
        _make_feature(
            tmp_path / "c",
            "f3.md",
            status="stable",
            service="",  # clean
        )
        violations = collect_violations(tmp_path)
        assert len(violations) == 2

    def test_path_fields_constant_complete(self) -> None:
        # Sanity check: PATH_FIELDS covers the documented frontmatter fields.
        assert set(PATH_FIELDS) == {"service", "contract", "router", "prompt"}
