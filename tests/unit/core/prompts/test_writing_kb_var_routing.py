"""Regression guard: every ``kb_*`` writing-template variable must be routable.

Background (CR-04, happened twice): a contributor adds a new ``{{kb_foo}}`` to
the writing templates, ``WritingContext.to_prompt_variables()``, and
``SYSTEM_VARS`` — but forgets to declare it optional in
``_COMMON_OPTIONAL_VARIABLES``. Writing routes that do NOT run full KB assembly
(REWRITE, EXTEND, … build a minimal ``extra`` dict instead of a full
WritingContext) then hit ``PromptVariableError`` at compose time and abort the
SSE stream. ``kb_other`` / ``kb_context_warnings`` were the two most recent
instances of this exact gap.

Why this is the right structural invariant
------------------------------------------
The PromptComposer feeds ``prepare_variables_for_template`` the union of
``context.as_variables()`` and ``route.optional_variables`` (composer.py). A
template placeholder raises iff it is (a) registered in the taxonomy, (b) absent
from the supplied variables, AND (c) absent from the route's optional set.
Writing routes share ``_COMMON_OPTIONAL_VARIABLES`` as their optional base, so
declaring a ``kb_*`` var there guarantees EVERY writing route renders it as ``""``
when no KB context is assembled (RULE-11 graceful degradation). Membership in
``WritingContext.to_prompt_variables()`` alone is NOT sufficient — that dict only
reaches the composer for routes that actually build a WritingContext, which is
precisely what REWRITE/EXTEND skip.

Legacy exception
----------------
``kb_characters`` / ``kb_locations`` pre-date this optional-set convention and
are instead supplied by every writing pipeline's ``extra`` dict
(see ``pipeline_rewrite.py``, ``pipeline_extend.py``, …). They are tracked in
``_LEGACY_PIPELINE_SUPPLIED_KB_VARS`` and carry the SAME latent risk that bit
``kb_other`` / ``kb_context_warnings`` — a pipeline that forgets to supply them
will crash the stream. They SHOULD be migrated into
``_COMMON_OPTIONAL_VARIABLES`` (RULE-11) as a follow-up; until then, new
``kb_*`` variables MUST NOT be added to the legacy set — declare them optional
instead, or this test will fail.
"""

from __future__ import annotations

import re

from narrare_core.prompts.route_table import _COMMON_OPTIONAL_VARIABLES
from tests.unit.core._bundled import bundled_prompts_root

_KB_VAR_RE = re.compile(r"\{\{(kb_\w+)\}\}")

# Pre-existing kb_* vars supplied by writing pipelines' ``extra`` dicts rather
# than declared optional. DO NOT ADD NEW ENTRIES — new kb_* vars must be
# declared in _COMMON_OPTIONAL_VARIABLES. Tracked for future RULE-11 migration.
_LEGACY_PIPELINE_SUPPLIED_KB_VARS: frozenset[str] = frozenset({"kb_characters", "kb_locations"})


def _writing_template_kb_vars() -> set[str]:
    """Every ``{{kb_*}}`` variable referenced by any bundled writing template."""
    root = bundled_prompts_root() / "writing" / "en"
    found: set[str] = set()
    for template_path in sorted(root.glob("*/system.md")):
        found.update(_KB_VAR_RE.findall(template_path.read_text()))
    return found


class TestWritingKbVarsRoutable:
    """Every ``kb_*`` writing-template variable must resolve on every route."""

    def test_discovery_finds_kb_variables(self) -> None:
        """Sanity: the glob/regex actually discovers kb_* placeholders."""
        kb_vars = _writing_template_kb_vars()
        assert kb_vars, "no kb_* variables discovered — bundled-template glob is misconfigured"
        # A few known-stable members anchor the discovery so silent regressions
        # in glob/regex surface immediately.
        assert {"kb_factions", "kb_relationships", "kb_suggested"} <= kb_vars

    def test_writing_kb_vars_are_optional_or_legacy(self) -> None:
        """Every kb_* template var is optional, save the documented legacy set.

        Fails (naming the offender) the moment a new kb_* variable is added to a
        writing template without also being declared in
        ``_COMMON_OPTIONAL_VARIABLES`` — the exact CR-04 regression class.
        """
        kb_vars = _writing_template_kb_vars()

        uncovered = kb_vars - set(_COMMON_OPTIONAL_VARIABLES)
        new_gaps = uncovered - _LEGACY_PIPELINE_SUPPLIED_KB_VARS

        assert not new_gaps, (
            "kb_* writing-template variable(s) not declared optional in "
            f"_COMMON_OPTIONAL_VARIABLES: {sorted(new_gaps)}. Add them to "
            "_COMMON_OPTIONAL_VARIABLES in route_table.py so writing routes "
            "without full KB assembly (REWRITE, EXTEND, …) render them as empty "
            "instead of raising PromptVariableError (RULE-11 graceful "
            "degradation). Do NOT add them to _LEGACY_PIPELINE_SUPPLIED_KB_VARS."
        )
