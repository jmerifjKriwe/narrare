"""Unit tests for scripts/doc_drift/agent_name_checks.py (review-04 AUFG-04-15).

The agent-name drift check scans markdown docs for subagent name references
that do not match the real definitions in
``.opencode/agents/subagents/narrare-dev/*.md``. Tests cover real-name
extraction from frontmatter, invalid-name detection, negation exclusions,
package-context exclusions, and integration via ``check_agent_name_drift()``.

See: review-04-dx-tooling.md AUFG-04-15.
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"


def _load_module():
    """Load agent_name_checks via the doc_drift package import path."""
    sys.path.insert(0, str(_SCRIPTS_DIR))
    try:
        # Force a fresh import so REPO_ROOT/_SCRIPTS_DIR resolve correctly.
        # Pop the WHOLE doc_drift family — popping only selected submodules
        # would orphan the siblings in sys.modules while the fresh parent
        # package loses their attributes (breaks later string-path
        # monkeypatching of any doc_drift.* module).
        for name in [
            n for n in list(sys.modules) if n == "doc_drift" or n.startswith("doc_drift.")
        ]:
            sys.modules.pop(name, None)
        import doc_drift.agent_name_checks as mod  # type: ignore[import-not-found]

        return mod
    finally:
        with contextlib.suppress(ValueError):
            sys.path.remove(str(_SCRIPTS_DIR))


@pytest.fixture()
def checker():
    return _load_module()


# ── Frontmatter extraction ──────────────────────────────────────


class TestExtractFrontmatter:
    """YAML frontmatter block extraction."""

    def test_standard_frontmatter(self, checker) -> None:
        content = "---\nname: Foo\ndescription: bar\n---\n# Body\n"
        fm = checker._extract_frontmatter(content)
        assert fm is not None
        assert "name: Foo" in fm

    def test_no_frontmatter(self, checker) -> None:
        content = "# Just a heading\n\nNo frontmatter.\n"
        assert checker._extract_frontmatter(content) is None

    def test_empty_frontmatter(self, checker) -> None:
        content = "---\n---\n# Body\n"
        fm = checker._extract_frontmatter(content)
        assert fm is not None
        assert fm.strip() == ""


# ── Real name extraction ────────────────────────────────────────


class TestGetRealNames:
    """Subagent name extraction from frontmatter definitions."""

    def test_real_names_from_repo(self, checker) -> None:
        """The real repo should yield all six specialists."""
        names = checker.get_real_subagent_names()
        assert "NarrareArchitectureSpecialist" in names
        assert "NarrareBackendSpecialist" in names
        assert "NarrareCoreSpecialist" in names
        assert "NarrareFrontendSpecialist" in names
        assert "NarrarePlatformSpecialist" in names
        assert "NarrareDocsSpecialist" in names

    def test_names_from_temp_dir(self, checker, tmp_path: Path) -> None:
        sub = tmp_path / "subs"
        sub.mkdir()
        (sub / "arch.md").write_text(
            "---\nname: NarrareArchSpecialist\n---\nBody\n", encoding="utf-8"
        )
        (sub / "core.md").write_text(
            "---\nname: NarrareCoreSpecialist\n---\nBody\n", encoding="utf-8"
        )
        names = checker.get_real_subagent_names(sub)
        assert "NarrareArchSpecialist" in names
        assert "NarrareCoreSpecialist" in names

    def test_template_placeholder_skipped(self, checker, tmp_path: Path) -> None:
        """``name: [Feature Name]`` is a placeholder, not a real name."""
        sub = tmp_path / "subs"
        sub.mkdir()
        (sub / "tmpl.md").write_text("---\nname: [Feature Name]\n---\nBody\n", encoding="utf-8")
        names = checker.get_real_subagent_names(sub)
        assert len(names) == 0

    def test_missing_dir_returns_empty(self, checker, tmp_path: Path) -> None:
        assert checker.get_real_subagent_names(tmp_path / "nope") == frozenset()


# ── _scan_file: invalid name detection ──────────────────────────


class TestScanFile:
    """Single-file scanning: fake names flagged, real names clean."""

    def test_subagent_type_invalid_is_critical(self, checker, tmp_path: Path) -> None:
        f = tmp_path / "doc.md"
        f.write_text(
            'Agent(subagent_type="narrare-architecture")\n',
            encoding="utf-8",
        )
        names = frozenset({"NarrareArchitectureSpecialist"})
        findings = checker._scan_file(f, names)
        assert len(findings) == 1
        assert findings[0].severity == "critical"
        assert "AGENT-NAME-DRIFT" in findings[0].message
        assert "narrare-architecture" in findings[0].message

    def test_subagent_type_valid_no_finding(self, checker, tmp_path: Path) -> None:
        f = tmp_path / "doc.md"
        f.write_text(
            'Agent(subagent_type="NarrareArchitectureSpecialist")\n',
            encoding="utf-8",
        )
        names = frozenset({"NarrareArchitectureSpecialist"})
        assert checker._scan_file(f, names) == []

    def test_backtick_narrare_name_flagged(self, checker, tmp_path: Path) -> None:
        f = tmp_path / "doc.md"
        f.write_text("Route to `narrare-implementation`.\n", encoding="utf-8")
        names = frozenset({"NarrareBackendSpecialist"})
        findings = checker._scan_file(f, names)
        assert len(findings) == 1
        assert "narrare-implementation" in findings[0].message
        assert "kebab-case" in findings[0].message

    def test_real_pascalcase_name_no_finding(self, checker, tmp_path: Path) -> None:
        f = tmp_path / "doc.md"
        f.write_text("Route to `NarrareBackendSpecialist`.\n", encoding="utf-8")
        names = frozenset({"NarrareBackendSpecialist"})
        assert checker._scan_file(f, names) == []

    def test_duplicate_invalid_deduped_per_file(self, checker, tmp_path: Path) -> None:
        f = tmp_path / "doc.md"
        f.write_text("Use `narrare-testing` and `narrare-testing` again.\n", encoding="utf-8")
        findings = checker._scan_file(f, frozenset())
        assert len(findings) == 1

    def test_unknown_narrare_identifier_not_flagged(self, checker, tmp_path: Path) -> None:
        """Unknown `` `narrare-api` `` (a service name) is not an agent reference."""
        f = tmp_path / "doc.md"
        f.write_text("Service name: `narrare-api`.\n", encoding="utf-8")
        assert checker._scan_file(f, frozenset()) == []

    def test_missing_file_returns_empty(self, checker, tmp_path: Path) -> None:
        assert checker._scan_file(tmp_path / "nope.md", frozenset()) == []


# ── Negation exclusions ─────────────────────────────────────────


class TestNegationExclusion:
    """Explanatory text (name does NOT exist) must not false-positive."""

    @pytest.mark.parametrize(
        "line",
        [
            "There is no `narrare-testing` specialist.",
            "NIEMALS `narrare-testing` verwenden.",
            "never use `narrare-implementation`.",
            "`narrare-testing` does not exist.",
            "These are fake names like `narrare-ui`.",
            "invented name `narrare-core`",
        ],
    )
    def test_negation_skipped(self, checker, tmp_path: Path, line: str) -> None:
        f = tmp_path / "d.md"
        f.write_text(line + "\n", encoding="utf-8")
        assert checker._scan_file(f, frozenset()) == []

    def test_actionable_on_different_line_flagged(self, checker, tmp_path: Path) -> None:
        """A negation line does not shield a phantom on a different line."""
        f = tmp_path / "d.md"
        f.write_text(
            "No `narrare-testing`.\nRoute to `narrare-implementation`.\n",
            encoding="utf-8",
        )
        findings = checker._scan_file(f, frozenset())
        assert len(findings) == 1
        assert "narrare-implementation" in findings[0].message


# ── Package-context exclusions ──────────────────────────────────


class TestPackageContextExclusion:
    """Package-install context must not false-positive on narrare-core."""

    def test_pip_install_excluded(self, checker, tmp_path: Path) -> None:
        f = tmp_path / "d.md"
        f.write_text(
            "Install with `pip install narrare-core[memory]`.\n",
            encoding="utf-8",
        )
        assert checker._scan_file(f, frozenset()) == []

    def test_extras_syntax_excluded(self, checker, tmp_path: Path) -> None:
        f = tmp_path / "d.md"
        f.write_text(
            "Optional: narrare-core[nlp] — graceful degradation.\n",
            encoding="utf-8",
        )
        assert checker._scan_file(f, frozenset()) == []

    def test_narrare_dev_directory_excluded(self, checker, tmp_path: Path) -> None:
        """``narrare-dev`` is a directory name, not an agent name."""
        f = tmp_path / "d.md"
        f.write_text(
            "Defined in .opencode/agents/subagents/narrare-dev/.\n",
            encoding="utf-8",
        )
        assert checker._scan_file(f, frozenset()) == []


# ── Integration: check_agent_name_drift ─────────────────────────


class TestCheckAgentNameDrift:
    """End-to-end integration tests."""

    def test_clean_repo_no_findings(self, checker) -> None:
        """The real repo (after fixes) should be clean."""
        findings = checker.check_agent_name_drift()
        critical = [f for f in findings if f.severity == "critical"]
        assert critical == []

    def test_phantom_in_docs(
        self,
        checker,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setattr(
            checker,
            "get_real_subagent_names",
            lambda: frozenset({"NarrareFooSpecialist"}),
        )
        monkeypatch.setattr(checker, "_AGENTS_MD", tmp_path / "nope.md")
        (tmp_path / "guide.md").write_text("Route to `narrare-implementation`.\n", encoding="utf-8")
        findings = checker.check_agent_name_drift(docs_dir=tmp_path)
        assert any("narrare-implementation" in f.message for f in findings)

    def test_phantom_subagent_type_in_docs(
        self,
        checker,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """An unknown subagent_type value is flagged even if not a known fake."""
        monkeypatch.setattr(
            checker,
            "get_real_subagent_names",
            lambda: frozenset({"NarrareFooSpecialist"}),
        )
        monkeypatch.setattr(checker, "_AGENTS_MD", tmp_path / "nope.md")
        (tmp_path / "guide.md").write_text(
            'Agent(subagent_type="narrare-database")\n', encoding="utf-8"
        )
        findings = checker.check_agent_name_drift(docs_dir=tmp_path)
        assert any("narrare-database" in f.message for f in findings)

    def test_general_subagent_type_allowed(
        self,
        checker,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """The built-in ``general`` subagent_type is valid, not flagged."""
        monkeypatch.setattr(
            checker,
            "get_real_subagent_names",
            lambda: frozenset({"NarrareFooSpecialist"}),
        )
        monkeypatch.setattr(checker, "_AGENTS_MD", tmp_path / "nope.md")
        (tmp_path / "guide.md").write_text('Agent(subagent_type="general")\n', encoding="utf-8")
        findings = checker.check_agent_name_drift(docs_dir=tmp_path)
        critical = [f for f in findings if f.severity == "critical"]
        assert critical == []

    def test_agents_md_scanned(
        self,
        checker,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """AGENTS.md (root-level, outside docs/) is scanned."""
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text('subagent_type="narrare-ghost"\n', encoding="utf-8")
        monkeypatch.setattr(checker, "_AGENTS_MD", agents_md)
        monkeypatch.setattr(
            checker,
            "get_real_subagent_names",
            lambda: frozenset({"NarrareFooSpecialist"}),
        )
        empty_docs = tmp_path / "empty_docs"
        empty_docs.mkdir()
        findings = checker.check_agent_name_drift(docs_dir=empty_docs)
        assert any("narrare-ghost" in f.message for f in findings)

    def test_empty_names_returns_warning(
        self,
        checker,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(checker, "get_real_subagent_names", lambda: frozenset())
        findings = checker.check_agent_name_drift()
        assert len(findings) == 1
        assert findings[0].severity == "warning"

    def test_archive_dir_skipped(
        self,
        checker,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setattr(
            checker,
            "get_real_subagent_names",
            lambda: frozenset({"NarrareFooSpecialist"}),
        )
        monkeypatch.setattr(checker, "_AGENTS_MD", tmp_path / "nope.md")
        (tmp_path / "archive").mkdir()
        (tmp_path / "archive" / "old.md").write_text("Use `narrare-testing`.\n", encoding="utf-8")
        assert checker.check_agent_name_drift(docs_dir=tmp_path) == []

    def test_superseded_adr_skipped(
        self,
        checker,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setattr(
            checker,
            "get_real_subagent_names",
            lambda: frozenset({"NarrareFooSpecialist"}),
        )
        monkeypatch.setattr(checker, "_AGENTS_MD", tmp_path / "nope.md")
        (tmp_path / "ADR-001-x.md").write_text(
            "# ADR-001\n\n> **Status:** ⛔ Superseded by ADR-002\n\nUse `narrare-testing`.\n",
            encoding="utf-8",
        )
        assert checker.check_agent_name_drift(docs_dir=tmp_path) == []
