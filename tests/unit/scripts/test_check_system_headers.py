"""Tests for the PROMPT-L2-HEADERS governance gate (R2 Slice 0).

Rule: every registry-governed ``prompts/_bundled/**/system.md`` may use
``^## `` level-2 headers ONLY for ``System Prompt`` and ``First Message``.
Rationale: ``extract_section`` (frontmatter.py) terminates the System Prompt
at the next ``^##\\s`` header — any other level-2 header silently truncates
the prompt at parse time (2026-09-10 boundary defect).

Coverage per the R2 Slice 0 brief:
1. Well-formed template (only allowed L2 headers) → clean.
2. Rogue ``## Foo`` header → [UNALLOWED] violation naming the template path.
3. Allowlisted rogue template → advisory-clean (approved exception).
4. Allowlist entry whose template got fixed → [STALE-ALLOWLIST] violation
   (exit-failing, mirrors T3 stale-baseline semantics).
5. Capability-loaded categories (meta/universal/wiki) are out of scope —
   full-body renderers, not ``PromptRegistry._parse_prompt``.
6. Allowlist self-governance: malformed and duplicate entries fail.

All tests run against isolated temp trees (monkeypatched module ROOT and
baseline path); the real repo is never mutated.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.architecture._checkers import _check_system_headers  # noqa: E402
from scripts.architecture.types import CheckResult  # noqa: E402

_BUNDLED = Path("packages/core/narrare_core/prompts/_bundled")

_WELL_FORMED = """---
prompt_type: writing
prompt_version: "1.0.0"
---

## System Prompt

Write a chapter for {{project_title}}.

### Output Format

- Prose only

## First Message

Ready when you are.
"""

_ROGUE = """---
prompt_type: writing
prompt_version: "1.0.0"
---

## System Prompt

Write a chapter for {{project_title}}.

## Output Format

Prose only.

## Do NOT

Summarize.
"""


def _write_template(tmp_path: Path, rel_dir: str, body: str, *, name: str = "system.md") -> Path:
    path = tmp_path / _BUNDLED / rel_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _patch_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    allowlist: list[str],
) -> None:
    """Point the checker at a temp repo root with a temp baseline.

    The baseline is written at its conventional relative location
    (``scripts/architecture/ai-gate-baseline.json``) under the temp root, so a
    single ROOT patch repoints both the bundled-tree scan and the baseline.
    """
    baseline_path = tmp_path / "scripts" / "architecture" / "ai-gate-baseline.json"
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(
        json.dumps({"system_prompt_l2_header_allowlist": allowlist}), encoding="utf-8"
    )
    monkeypatch.setattr(_check_system_headers, "ROOT", tmp_path)


def _rel(tmp_path: Path, rel_dir: str) -> str:
    return (_BUNDLED / rel_dir / "system.md").as_posix()


# =====================================================================
# 1. Clean template
# =====================================================================


def test_well_formed_template_is_clean(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_environment(monkeypatch, tmp_path, [])
    _write_template(tmp_path, "writing/en/new_chapter", _WELL_FORMED)

    result = CheckResult()
    _check_system_headers.check_system_prompt_l2_headers(result)

    assert result.violations == []
    assert result.approved_exceptions == []


# =====================================================================
# 2. Rogue header → [UNALLOWED] violation naming the path
# =====================================================================


def test_rogue_header_produces_unallowed_violation_naming_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_environment(monkeypatch, tmp_path, [])
    _write_template(tmp_path, "writing/en/new_chapter", _ROGUE)

    result = CheckResult()
    _check_system_headers.check_system_prompt_l2_headers(result)

    rel = _rel(tmp_path, "writing/en/new_chapter")
    unallowed = [v for v in result.violations if v.detail.startswith("[UNALLOWED]")]
    assert len(unallowed) == 1
    assert str(unallowed[0].file) == rel
    assert rel in unallowed[0].detail
    assert "## Output Format" in unallowed[0].detail
    assert "## Do NOT" in unallowed[0].detail
    # Violation points at the first offending header line (absolute line):
    # frontmatter (4 lines incl. delimiters) + blank + header + blank + text
    # + blank → "## Output Format" sits on line 10 of the file.
    assert unallowed[0].line == 10
    assert unallowed[0].rule == "PROMPT-L2-HEADERS"


# =====================================================================
# 3. Allowlisted rogue template → advisory-clean
# =====================================================================


def test_allowlisted_rogue_template_is_advisory_clean(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rel = _rel(tmp_path, "writing/en/new_chapter")
    _patch_environment(
        monkeypatch,
        tmp_path,
        [f"{rel} | rogue headers pending demotion | R2 demotion slice pending"],
    )
    _write_template(tmp_path, "writing/en/new_chapter", _ROGUE)

    result = CheckResult()
    _check_system_headers.check_system_prompt_l2_headers(result)

    assert result.violations == []
    assert len(result.approved_exceptions) == 1
    advisory = result.approved_exceptions[0]
    assert advisory.approved is True
    assert str(advisory.file) == rel
    assert "R2 demotion slice pending" in advisory.approval_reason
    assert "rogue headers pending demotion" in advisory.approval_reason


# =====================================================================
# 4. Fixed template → [STALE-ALLOWLIST] failure
# =====================================================================


def test_allowlist_entry_for_fixed_template_fails_stale(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rel = _rel(tmp_path, "writing/en/new_chapter")
    entry = f"{rel} | rogue headers pending demotion | R2 demotion slice pending"
    _patch_environment(monkeypatch, tmp_path, [entry])
    _write_template(tmp_path, "writing/en/new_chapter", _WELL_FORMED)

    result = CheckResult()
    _check_system_headers.check_system_prompt_l2_headers(result)

    stale = [v for v in result.violations if v.detail.startswith("[STALE-ALLOWLIST]")]
    assert len(stale) == 1
    assert rel in stale[0].detail
    # Exit-failing: emitted as a violation, never as an advisory exception.
    assert not any("STALE-ALLOWLIST" in v.detail for v in result.approved_exceptions)


def test_allowlist_entry_for_deleted_template_fails_stale(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rel = _rel(tmp_path, "writing/en/ghost")
    entry = f"{rel} | rogue headers pending demotion | R2 demotion slice pending"
    _patch_environment(monkeypatch, tmp_path, [entry])
    _write_template(tmp_path, "writing/en/new_chapter", _WELL_FORMED)

    result = CheckResult()
    _check_system_headers.check_system_prompt_l2_headers(result)

    assert len([v for v in result.violations if "[STALE-ALLOWLIST]" in v.detail]) == 1


# =====================================================================
# 5. Scope discriminator — capability-loaded categories are exempt
# =====================================================================


def test_capability_categories_are_out_of_scope(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """meta/universal/wiki render the full body (Capabilities / WikiPromptLoader),
    so level-2 headers there do not hit the extract_section truncation path."""
    _patch_environment(monkeypatch, tmp_path, [])
    for category in ("meta", "universal", "wiki"):
        _write_template(tmp_path, f"{category}/en", _ROGUE)

    result = CheckResult()
    _check_system_headers.check_system_prompt_l2_headers(result)

    assert result.violations == []
    assert result.approved_exceptions == []


# =====================================================================
# 6. Allowlist self-governance
# =====================================================================


def test_malformed_allowlist_entry_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_environment(monkeypatch, tmp_path, ["no-pipe-separators-at-all"])
    _write_template(tmp_path, "writing/en/new_chapter", _WELL_FORMED)

    result = CheckResult()
    _check_system_headers.check_system_prompt_l2_headers(result)

    malformed = [v for v in result.violations if v.detail.startswith("[MALFORMED-ALLOWLIST]")]
    assert len(malformed) == 1


def test_duplicate_allowlist_entry_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rel = _rel(tmp_path, "writing/en/new_chapter")
    entry = f"{rel} | rogue headers pending demotion | R2 demotion slice pending"
    _patch_environment(monkeypatch, tmp_path, [entry, entry])
    _write_template(tmp_path, "writing/en/new_chapter", _ROGUE)

    result = CheckResult()
    _check_system_headers.check_system_prompt_l2_headers(result)

    dup = [v for v in result.violations if v.detail.startswith("[DUPLICATE-ALLOWLIST]")]
    assert len(dup) == 1
