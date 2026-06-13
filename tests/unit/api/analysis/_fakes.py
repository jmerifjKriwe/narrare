"""Shared Fake classes for analysis service unit tests.

Centralises Fake agent classes used across multiple test files
to avoid duplication and keep each test file within RULE-04 limits.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from narrare_core.agents.pov_types import POVDetectionOutput
from narrare_core.agents.readability_types import ReadabilityAgentOutput
from tests.fakes._shared import CallRecord

if TYPE_CHECKING:
    from uuid import UUID


class FakePOVAgent:
    """Fake POVDetectionAgent — returns a predetermined output or raises."""

    def __init__(
        self,
        output: POVDetectionOutput | None = None,
        error: Exception | None = None,
    ) -> None:
        self._output = output or POVDetectionOutput(overall_assessment="ok")
        self._error = error
        self.run_called: bool = False
        self.last_deps: Any = None

    async def run(self, prompt: str, deps: Any = None, **kwargs: Any) -> POVDetectionOutput:
        self.run_called = True
        self.last_deps = deps
        if self._error:
            raise self._error
        return self._output


class FakeReadabilityAgent:
    """Fake ReadabilityAgent — returns predetermined output or raises."""

    def __init__(
        self,
        output: ReadabilityAgentOutput | None = None,
        error: Exception | None = None,
    ) -> None:
        self._output = output or ReadabilityAgentOutput(overall_assessment="Good.")
        self._error = error
        self.run_called: bool = False
        self.last_deps: Any = None

    async def run(self, prompt: str, deps: Any = None, **kwargs: Any) -> ReadabilityAgentOutput:
        self.run_called = True
        self.last_deps = deps
        if self._error:
            raise self._error
        return self._output


class SeededKBRepository:
    """KB repo stub returning seeded character names from list_entries.

    Standalone stub (does not inherit FakeKBRepository) — only
    ``list_entries`` is exercised by the analysis service tests.
    """

    def __init__(self, character_names: list[str]) -> None:
        self._names = character_names
        self.calls: list[CallRecord] = []

    async def list_entries(
        self,
        novel_id: UUID,
        entity_type: str | None = None,
        tags: list[str] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Any], int]:
        self.calls.append(CallRecord("list_entries"))
        entries = [type("Entry", (), {"name": n})() for n in self._names]
        return entries, len(entries)
