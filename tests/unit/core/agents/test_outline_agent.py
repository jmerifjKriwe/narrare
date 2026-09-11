"""Tests für OutlineAgent — Instantiation und Output-Typen.

Test-Strategie:
- TestModel für deterministische Agent-Tests
- Validator-Tests live in ``test_outline_validation.py`` (ADR-035)
- Keine echten LLM-Calls (RULE-01b)
"""

from __future__ import annotations

from pydantic_ai.models.test import TestModel

from narrare_core.agents.outline_agent import OutlineAgent, OutlineDeps
from narrare_core.agents.outline_types import OutlineOutput

# ---------------------------------------------------------------------------
# A. OutlineDeps
# ---------------------------------------------------------------------------


class TestOutlineDeps:
    """OutlineDeps erzeugt und konfiguriert korrekt."""

    def test_defaults(self) -> None:
        deps = OutlineDeps()
        assert deps.genre == ""
        assert deps.tone == "balanced"
        assert deps.language == "en"

    def test_custom_values(self) -> None:
        deps = OutlineDeps(genre="Fantasy", tone="dark", language="de")
        assert deps.genre == "Fantasy"
        assert deps.tone == "dark"
        assert deps.language == "de"


# ---------------------------------------------------------------------------
# B. OutlineOutput
# ---------------------------------------------------------------------------


class TestOutlineOutput:
    """OutlineOutput validiert korrekt."""

    def test_defaults(self) -> None:
        output = OutlineOutput()
        assert output.chapter_title == ""
        assert output.scenes == []
        assert output.outline_text == ""

    def test_with_values(self) -> None:
        output = OutlineOutput(
            chapter_title="The Dark Forest",
            scenes=["Scene 1: Entry", "Scene 2: Discovery"],
            outline_text="Full outline text",
        )
        assert output.chapter_title == "The Dark Forest"
        assert len(output.scenes) == 2
        assert output.outline_text == "Full outline text"


# ---------------------------------------------------------------------------
# C. OutlineAgent — Instantiation
# ---------------------------------------------------------------------------


class TestOutlineAgent:
    """OutlineAgent instantiiert und executed korrekt."""

    def test_can_be_instantiated(self) -> None:
        model = TestModel()
        agent = OutlineAgent(model=model)
        assert isinstance(agent, OutlineAgent)
        assert agent._agent is not None

    def test_can_be_instantiated_with_test_model(self) -> None:
        """Mit TestModel (kein echter LLM-Call)."""
        model = TestModel()
        agent = OutlineAgent(model=model)
        assert isinstance(agent, OutlineAgent)
        assert agent._agent is not None
