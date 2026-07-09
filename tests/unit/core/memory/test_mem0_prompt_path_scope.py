"""RULE-02b scope boundary for the mem0 client (ADR-064).

``mem0_client.py`` carries extraction prompts (``_WRITING_PREFERENCE_PROMPTS``)
and forwards ``custom_instructions`` to the mem0 library's config dict. These are
third-party-library config strings consumed by mem0's internal extraction LLM —
they are NOT Narrare prompt-resolution paths, so they sit outside RULE-02b's
enforcement surface.

This test locks that boundary in two complementary ways:

1. **Scope check** — the RULE-02b checker (``check_prompt_registry_access``)
   returns NO violations for ``mem0_client.py``: it neither calls
   ``PromptRegistry.resolve()`` nor imports ``PromptRegistry``. If a future
   change adds such a call/import, this test fails until the prompt path is
   routed through ``PromptComposer`` (or a real governed exception is filed).
2. **Registration check** — the governed exception is registered in
   ``pyproject.toml [tool.narrare.architecture.exceptions]`` (RULE-02b →
   mem0_client.py), proving the boundary decision is documented (ADR-064/ADR-028)
   rather than silently relied upon — it cannot silently disappear.

See: ADR-064, ADR-028.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import pytest
from scripts.architecture._checkers.prompt_path import check_prompt_registry_access

# Stable repo-relative path — matches the entry registered in pyproject.toml
# [tool.narrare.architecture.exceptions] and what the checker's
# relative_to_root() produces.
REPO_ROOT = Path(__file__).resolve().parents[4]
MEM0_CLIENT_REL = "packages/core/narrare_core/memory/mem0_client.py"
PYPROJECT = REPO_ROOT / "pyproject.toml"


@pytest.mark.mutation_inert
class TestMem0ClientRule02bScope:
    """ADR-064: mem0_client.py is outside RULE-02b's enforcement surface."""

    def test_prompt_path_checker_flags_nothing(self) -> None:
        """The RULE-02b checker produces zero violations for mem0_client.py.

        This is the scope boundary: the file neither resolves prompts via
        ``PromptRegistry`` nor imports it. If a future change adds such a
        call/import, this test fails until the prompt path is routed through
        ``PromptComposer`` (or a real governed exception is registered).
        """
        source = (REPO_ROOT / MEM0_CLIENT_REL).read_text(encoding="utf-8")
        tree = ast.parse(source)
        violations = check_prompt_registry_access(MEM0_CLIENT_REL, tree, source.splitlines())
        assert violations == [], (
            f"mem0_client.py must be outside RULE-02b scope, but got: {violations}"
        )

    def test_rule02b_exception_is_registered_in_pyproject(self) -> None:
        """The RULE-02b governed exception for mem0_client.py is registered.

        ADR-064/ADR-028 require every architecture exception to be registered in
        ``pyproject.toml``. Asserting this here proves the boundary is documented
        rather than silently relied upon — the exception cannot silently
        disappear without this test noticing.
        """
        pyproject = tomllib.loads(PYPROJECT.read_text())
        entries = (
            pyproject.get("tool", {})
            .get("narrare", {})
            .get("architecture", {})
            .get("exceptions", {})
            .get("entries", [])
        )
        registered = {(entry.get("rule"), entry.get("file")) for entry in entries}
        assert ("RULE-02b", MEM0_CLIENT_REL) in registered, (
            "RULE-02b exception for mem0_client.py must be registered in "
            "pyproject.toml [tool.narrare.architecture.exceptions] (ADR-064)"
        )
