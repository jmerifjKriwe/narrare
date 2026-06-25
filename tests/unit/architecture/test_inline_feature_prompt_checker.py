"""Regression tests for the ADR-049 A5 INLINE-FEATURE-PROMPT checker.

Verifies that the checker:
1. Flags ``agent.run(prompt=f"...")`` with feature-framing in service-layer files.
2. Does NOT flag pure-runtime-data prompts (``agent.run(prompt=chapter.text)``).
3. Does NOT flag agent calls outside apps/api/.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from scripts.architecture._checkers._check_inline_feature_prompt import (
    check_inline_feature_prompt,
)

if TYPE_CHECKING:
    from scripts.architecture.types import Violation


def _check_source(rel_path: str, source: str) -> list[Violation]:
    """Parse source and run the A5 checker."""
    tree = ast.parse(source, filename=rel_path)
    return check_inline_feature_prompt(rel_path, tree, source.splitlines())


def test_a5_flags_f_string_feature_prompt() -> None:
    """A5: ``agent.run(prompt=f"Analyse the timeline...")`` is flagged."""
    source = (
        "async def call(agent, novel):\n"
        "    result = await agent.run(\n"
        "        prompt=f\"Analyse the timeline for '{novel.title}'. Genre: {novel.genre}\",\n"
        "        deps=None,\n"
        "    )\n"
        "    return result\n"
    )
    violations = _check_source("apps/api/narrare/planning/timeline_service.py", source)
    assert len(violations) == 1
    assert violations[0].rule == "INLINE-FEATURE-PROMPT"


def test_a5_flags_concatenated_feature_prompt() -> None:
    """A5: ``agent.run(prompt="Generate a summary. " + text)`` is flagged."""
    source = (
        "async def call(agent, text):\n"
        "    result = await agent.run(\n"
        '        prompt="Generate a chapter summary.\\n\\n" + text,\n'
        "    )\n"
        "    return result\n"
    )
    violations = _check_source("apps/api/narrare/writing/service.py", source)
    assert len(violations) == 1
    assert violations[0].rule == "INLINE-FEATURE-PROMPT"


def test_a5_allows_pure_runtime_data_prompt() -> None:
    """A5: ``agent.run(prompt=chapter.text)`` is NOT flagged (runtime data)."""
    source = (
        "async def call(agent, chapter):\n"
        "    result = await agent.run(\n"
        "        prompt=chapter.content,\n"
        "        deps=None,\n"
        "    )\n"
        "    return result\n"
    )
    violations = _check_source("apps/api/narrare/writing/service.py", source)
    assert violations == []


def test_a5_allows_composed_user_prompt_variable() -> None:
    """A5: ``agent.run(prompt=composed.user)`` is NOT flagged (variable reference)."""
    source = (
        "async def call(agent, composed):\n"
        "    result = await agent.run(\n"
        "        prompt=composed.user,\n"
        "        deps=None,\n"
        "    )\n"
        "    return result\n"
    )
    violations = _check_source("apps/api/narrare/writing/service.py", source)
    assert violations == []


def test_a5_ignores_non_service_files() -> None:
    """A5: files outside apps/api/ are NOT scanned."""
    source = (
        "async def call(agent, novel):\n"
        "    result = await agent.run(\n"
        "        prompt=f\"Analyse the timeline for '{novel.title}'.\",\n"
        "    )\n"
        "    return result\n"
    )
    # Core package, not service layer
    violations = _check_source("packages/core/narrare_core/planning/agent.py", source)
    assert violations == []


def test_a5_flags_run_stream_method() -> None:
    """A5: ``agent.run_stream(prompt=f"Generate...")`` is also flagged."""
    source = (
        "async def call(agent):\n"
        "    async for chunk in agent.run_stream(\n"
        '        prompt=f"Generate a story outline for {topic}",\n'
        "    ):\n"
        "        yield chunk\n"
    )
    violations = _check_source("apps/api/narrare/writing/service.py", source)
    assert len(violations) == 1
    assert violations[0].rule == "INLINE-FEATURE-PROMPT"


def test_a5_allows_fstring_without_feature_framing() -> None:
    """A5: ``agent.run(prompt=f"{user_message}")`` without feature verbs is NOT flagged."""
    source = (
        "async def call(agent, user_message):\n"
        "    result = await agent.run(\n"
        '        prompt=f"{user_message}",\n'
        "    )\n"
        "    return result\n"
    )
    violations = _check_source("apps/api/narrare/writing/service.py", source)
    assert violations == []


def test_a5_real_repo_baseline_count() -> None:
    """The real repo has zero A5 violations after ADR-054 debt retirement.

    ADR-054 migrated the last three ratcheted services (CharacterArcService,
    TimelineExtractionService, KBMergeService) to PromptComposer Mode 1 and
    emptied ``_BASELINE_VIOLATIONS``. The ratchet floor is now zero: any new
    inline feature-prompt is blocking, with no approved debt baseline to
    hide behind. This test guards both halves of that invariant — no
    blocking violations AND no approved baseline violations.
    """
    from scripts.architecture.helpers import ROOT, relative_to_root

    total_blocking = 0
    total_approved = 0
    api_dir = ROOT / "apps" / "api"
    for py_file in api_dir.rglob("*.py"):
        if any(p in str(py_file) for p in [".venv", "__pycache__", "migrations"]):
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except OSError, SyntaxError:
            continue
        rel = relative_to_root(py_file)
        for v in check_inline_feature_prompt(rel, tree, source.splitlines()):
            if v.approved:
                total_approved += 1
            else:
                total_blocking += 1

    assert total_blocking == 0, (
        f"New (non-baselined) A5 violations found: {total_blocking}. "
        "Either fix them or add to the baseline (with a disclosing ADR)."
    )
    assert total_approved == 0, (
        f"Expected 0 baseline A5 violations (ADR-054 retired the floor), "
        f"got {total_approved}. If violations were re-baselined, update "
        "this assertion and _check_inline_feature_prompt.py."
    )


def test_a5_baseline_constant_is_empty() -> None:
    """ADR-054 D10: ``_BASELINE_VIOLATIONS`` is empty (zero ratchet floor)."""
    from scripts.architecture._checkers._check_inline_feature_prompt import (
        _BASELINE_VIOLATIONS,
    )

    assert frozenset() == _BASELINE_VIOLATIONS, (
        "ADR-054 retired the three baseline entries; the ratchet floor must "
        "be zero. Re-baselining requires a disclosing ADR."
    )


def test_a5_synthetic_violation_is_blocking() -> None:
    """ADR-054 D10: with an empty baseline, a synthetic inline feature-prompt
    is flagged as a BLOCKING (non-approved) violation — proving the gate
    still catches new debt now that no ratchet floor hides it.
    """
    source = (
        "async def call(agent, novel):\n"
        "    result = await agent.run(\n"
        '        prompt=f"Generate a character arc for {novel.title}",\n'
        "    )\n"
        "    return result\n"
    )
    violations = _check_source("apps/api/narrare/planning/character_arc_service.py", source)
    assert len(violations) == 1
    assert violations[0].rule == "INLINE-FEATURE-PROMPT"
    assert violations[0].approved is False, (
        "With an empty baseline (ADR-054 D10), a new inline feature-prompt "
        "must be blocking, not an approved exception."
    )
