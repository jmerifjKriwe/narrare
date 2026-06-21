"""Deterministic evaluators for kb_operations evals.

Each evaluator is metadata-aware: it inspects the case's ``agent_type`` and
returns ``1.0`` (not applicable) for cases belonging to the other agents,
mirroring the ``planning_structure`` suite pattern. When applicable, it asserts
REAL schema/range properties of the agent output shapes — no stubs.

Validated output schemas (file:symbol):

- KBAgent        → ``narrare_core.agents.kb_agent.KBAgent`` tool methods
- KBAssistAgent → ``narrare_core.agents.kb_assist_types.KBAssistOutput``
- KBImproveAgent→ ``narrare_core.agents.kb_improve_types.KBImproveOutput``
- KBMergeAgent  → ``narrare_core.agents.merge_types.MergeOutput``

Known value sets are sourced authoritatively from the core type modules and
agent validators. ``KBAgent`` has no direct output model; its evaluated surface
is the actual tool operation schema exposed by ``get_toolset()``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from evals.models import KBOperationsResult
from narrare_core.agents.kb_improve_types import SuggestionType

# ---------------------------------------------------------------------------
# Authoritative value sets (mirror actual code contracts).
# ---------------------------------------------------------------------------

# From kb_agent.KBAgent tool methods.
_KB_AGENT_OPERATIONS: frozenset[str] = frozenset(
    {"search_kb", "get_entity", "get_related_entities"}
)

# From kb_agent.KBAgent.search_kb docstring.
_KB_ENTITY_TYPES: frozenset[str] = frozenset(
    {"character", "location", "faction", "object", "system", "timeline", "concept", "setting"}
)

# From kb_assist_types.KBAssistOutput.mode Literal.
_KB_ASSIST_MODES: frozenset[str] = frozenset({"question", "suggestion", "draft", "complete"})

# From kb_improve_types.SuggestionType.
_IMPROVEMENT_TYPES: frozenset[str] = frozenset(item.value for item in SuggestionType)

# From merge_agent.KBMergeAgent._validate_output.
_MERGE_DECISIONS: frozenset[str] = frozenset({"merge", "distinct", "uncertain"})


def _score(checks: list[bool]) -> float:
    """Return the fraction of satisfied checks (0.0 when there are none)."""

    if not checks:
        return 0.0
    return sum(1 for ok in checks if ok) / len(checks)


@dataclass
class KBAgentOperationSchemaValidator(Evaluator[Any, KBOperationsResult, dict[str, Any]]):
    """Validate KB intent routing and entity operation schema for KBAgent.

    Not applicable (returns 1.0) when the case ``agent_type`` is not
    ``kb_agent``. When applicable, checks the real tool operation names and
    operation-specific argument fields.
    """

    def evaluate(self, ctx: EvaluatorContext[Any, KBOperationsResult, dict[str, Any]]) -> float:
        if not ctx.metadata or ctx.metadata.get("agent_type") != "kb_agent":
            return 1.0

        section = ctx.output.kb_agent
        if section is None:
            return 0.0

        checks: list[bool] = [
            section.operation in _KB_AGENT_OPERATIONS,
            bool(section.formatted_response.strip()),
            section.entity_type in _KB_ENTITY_TYPES if section.entity_type is not None else True,
        ]

        if section.operation == "search_kb":
            checks.append(bool(section.query.strip()))
        elif section.operation == "get_entity":
            checks.append(bool(section.entity_name.strip()))
        elif section.operation == "get_related_entities":
            checks.append(bool(section.entity_name.strip()))
            checks.append(section.relation_type is None or bool(section.relation_type.strip()))
        else:
            checks.append(False)

        return _score(checks)


@dataclass
class KBAssistSchemaValidator(Evaluator[Any, KBOperationsResult, dict[str, Any]]):
    """Validate session output structure and field question-answer pairs.

    Mirrors ``KBAssistAgent._validate_output`` mode invariants: question mode
    needs ``question`` + ``field_key``; suggestion mode needs ``suggestion`` +
    ``field_key``; draft and complete modes need non-empty dict entries.
    """

    def evaluate(self, ctx: EvaluatorContext[Any, KBOperationsResult, dict[str, Any]]) -> float:
        if not ctx.metadata or ctx.metadata.get("agent_type") != "kb_assist":
            return 1.0

        section = ctx.output.kb_assist
        if section is None:
            return 0.0

        checks: list[bool] = [
            section.mode in _KB_ASSIST_MODES,
            0.0 <= section.progress <= 1.0 if section.progress is not None else True,
        ]

        if section.mode == "question":
            checks.extend(
                [
                    bool(section.question and section.question.strip()),
                    bool(section.field_key and section.field_key.strip()),
                ]
            )
        elif section.mode == "suggestion":
            checks.extend(
                [
                    bool(section.suggestion and section.suggestion.strip()),
                    bool(section.field_key and section.field_key.strip()),
                ]
            )
        elif section.mode == "draft":
            checks.append(_has_non_empty_pairs(section.draft_entry))
        elif section.mode == "complete":
            checks.append(_has_non_empty_pairs(section.final_entry))

        return _score(checks)


@dataclass
class KBImproveSchemaValidator(Evaluator[Any, KBOperationsResult, dict[str, Any]]):
    """Validate improvement suggestion schema and analysis notes fields.

    Mirrors ``KBImproveAgent`` invariants: every retained suggestion has a
    non-empty target and description; suggestion confidence and completeness
    score stay in [0.0, 1.0].
    """

    def evaluate(self, ctx: EvaluatorContext[Any, KBOperationsResult, dict[str, Any]]) -> float:
        if not ctx.metadata or ctx.metadata.get("agent_type") != "kb_improve":
            return 1.0

        section = ctx.output.kb_improve
        if section is None:
            return 0.0

        checks: list[bool] = [
            bool(section.overall_assessment.strip()),
            0.0 <= section.completeness_score <= 1.0,
            all(name.strip() for name in section.context_used) if section.context_used else True,
        ]

        for suggestion in section.suggestions:
            checks.extend(
                [
                    suggestion.type in _IMPROVEMENT_TYPES,
                    bool(suggestion.target.strip()),
                    bool(suggestion.description.strip()),
                    0.0 <= suggestion.confidence <= 1.0,
                ]
            )

        return _score(checks)


@dataclass
class KBMergeSchemaValidator(Evaluator[Any, KBOperationsResult, dict[str, Any]]):
    """Validate merge decision output and duplicate detection confidence.

    Mirrors ``KBMergeAgent._validate_output`` invariants and the
    ``MergeDecision`` confidence contract documented in ``merge_types.py``.
    """

    def evaluate(self, ctx: EvaluatorContext[Any, KBOperationsResult, dict[str, Any]]) -> float:
        if not ctx.metadata or ctx.metadata.get("agent_type") != "kb_merge":
            return 1.0

        section = ctx.output.kb_merge
        if section is None:
            return 0.0

        checks: list[bool] = [
            bool(section.overall_notes.strip()) if section.merge_decisions else True,
        ]
        seen_pair_ids: set[str] = set()
        for decision in section.merge_decisions:
            pair_id = decision.pair_id.strip()
            checks.extend(
                [
                    bool(pair_id),
                    pair_id not in seen_pair_ids,
                    decision.decision in _MERGE_DECISIONS,
                    0.0 <= decision.confidence <= 1.0,
                    bool(decision.reasoning.strip()),
                ]
            )
            seen_pair_ids.add(pair_id)
            if decision.decision == "merge":
                checks.append(decision.merge_strategy is not None)
                if decision.merge_strategy is not None:
                    checks.append(bool(decision.merge_strategy.keep_name.strip()))

        return _score(checks)


def _has_non_empty_pairs(value: dict[str, Any] | None) -> bool:
    """Return True when *value* is a non-empty dict with non-empty key/value pairs."""

    if not value:
        return False
    return all(str(key).strip() and str(item).strip() for key, item in value.items())
