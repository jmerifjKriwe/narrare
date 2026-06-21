"""Deterministic evaluators for analysis_metrics evals.

Each evaluator is metadata-aware: it inspects the case's ``agent_type`` and
returns ``1.0`` (not applicable) for cases belonging to the other agents,
mirroring the behaviour of ``ChatDraftStructureMatch``. When applicable, it
asserts REAL schema/range properties of the agent's output shape — no stubs.

Validated output schemas (file:symbol):

- ReadabilityAgent    → ``narrare_core.agents.readability_types.ReadabilityAgentOutput``
- POVDetectionAgent   → ``narrare_core.agents.pov_types.POVDetectionOutput``
- ChapterSummaryAgent → ``narrare_core.agents.summary_types.SummaryOutput``

Known value sets are sourced authoritatively from the agent type docstrings
and the POV agent's ``_VALID_ISSUE_TYPES`` / ``_VALID_SEVERITIES`` frozensets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from evals.models import AnalysisMetricsResult

# ---------------------------------------------------------------------------
# Authoritative value sets (mirror the agents' own contracts).
#
# NOTE: the eval-expansion-plan prose lists POV types as "1st/2nd/3rd/omniscient",
# but the ACTUAL ``POVDetectionOutput.analysis_type`` schema
# (``pov_types.py`` docstring) documents only ``third_limited``,
# ``first_person``, ``omniscient``, ``mixed`` — there is no ``second_person``.
# Per the architectural-discipline standard (documented != implemented;
# verify reality), evaluators validate against the real enum, not the plan's
# prose. Validating against a value the agent never produces would be a stub.
# ---------------------------------------------------------------------------

# From readability_types.SentenceIssue docstring.
_READABILITY_ISSUE_TYPES: frozenset[str] = frozenset(
    {"too_long", "complex_vocabulary", "passive_voice", "ambiguous"}
)

# From pov_types.POVDetectionOutput.analysis_type docstring.
# (Agent uses third_limited / first_person / omniscient / mixed — no 2nd person.)
_POV_ANALYSIS_TYPES: frozenset[str] = frozenset(
    {"third_limited", "first_person", "omniscient", "mixed"}
)

# From pov_agent.POVDetectionAgent._VALID_ISSUE_TYPES.
_POV_ISSUE_TYPES: frozenset[str] = frozenset(
    {"head_hop", "knowledge_leak", "emotional_leak", "physical_impossibility"}
)

# From pov_agent.POVDetectionAgent._VALID_SEVERITIES.
_POV_SEVERITIES: frozenset[str] = frozenset({"error", "warning"})

# Reasonable upper bound for a chapter-summary word count (the agent produces
# 2-4 sentences). Catches runaway/regressed outputs without over-constraining.
_SUMMARY_MAX_WORDS = 200


def _score(checks: list[bool]) -> float:
    """Return the fraction of satisfied checks (0.0 when there are none)."""

    if not checks:
        return 0.0
    return sum(1 for ok in checks if ok) / len(checks)


@dataclass
class ReadabilitySchemaValidator(Evaluator[Any, AnalysisMetricsResult, dict[str, Any]]):
    """Validate structured-output schema and metric-label consistency for ReadabilityAgent.

    Not applicable (returns 1.0) when the case ``agent_type`` is not ``readability``.
    When applicable, checks:

    - readability section present
    - overall_assessment non-empty (matches the agent's own invariant)
    - every problematic-sentence issue ``type`` is from the known set
      {too_long, complex_vocabulary, passive_voice, ambiguous}
    - every problematic sentence carries 0-3 suggestions
      (the agent promises "2-3 rewrite alternatives")
    """

    def evaluate(self, ctx: EvaluatorContext[Any, AnalysisMetricsResult, dict[str, Any]]) -> float:
        if not ctx.metadata or ctx.metadata.get("agent_type") != "readability":
            return 1.0

        section = ctx.output.readability
        if section is None:
            return 0.0

        checks: list[bool] = [
            bool(section.overall_assessment.strip()),
        ]

        if section.problematic_sentences:
            for sentence in section.problematic_sentences:
                raw_issues: object = sentence.get("issues")
                issues: list[Any] = (
                    cast("list[Any]", raw_issues) if isinstance(raw_issues, list) else []
                )
                if issues:
                    typed_issues: list[dict[str, Any]] = [
                        cast("dict[str, Any]", i) for i in issues if isinstance(i, dict)
                    ]
                    issue_types_ok = len(typed_issues) == len(issues) and all(
                        str(i.get("type", "")) in _READABILITY_ISSUE_TYPES for i in typed_issues
                    )
                    checks.append(issue_types_ok)
                else:
                    # A flagged sentence may legitimately have no typed issues.
                    checks.append(True)
                raw_suggestions: object = sentence.get("suggestions")
                suggestions_list: list[Any] = (
                    cast("list[Any]", raw_suggestions) if isinstance(raw_suggestions, list) else []
                )
                checks.append(0 <= len(suggestions_list) <= 3)
        else:
            # No problematic sentences is a valid result (clean passage).
            checks.append(True)
            checks.append(True)

        return _score(checks)


@dataclass
class POVDetectionSchemaValidator(Evaluator[Any, AnalysisMetricsResult, dict[str, Any]]):
    """Validate POV classification, confidence ranges, and issue taxonomy for POVDetectionAgent.

    Not applicable (returns 1.0) when the case ``agent_type`` is not ``pov``.
    When applicable, checks:

    - pov section present
    - analysis_type in the known set {third_limited, first_person, omniscient, mixed}
    - every scene.confidence in [0.0, 1.0]
    - every scene.pov_character non-empty (agent invariant)
    - every pov_distribution value in [0.0, 1.0]
    - every issue.type in the known POV issue set
    - every issue.severity in {error, warning}
    - switch_count >= 0
    - overall_assessment non-empty
    """

    def evaluate(self, ctx: EvaluatorContext[Any, AnalysisMetricsResult, dict[str, Any]]) -> float:
        if not ctx.metadata or ctx.metadata.get("agent_type") != "pov":
            return 1.0

        section = ctx.output.pov
        if section is None:
            return 0.0

        checks: list[bool] = [
            section.analysis_type in _POV_ANALYSIS_TYPES,
            bool(section.overall_assessment.strip()),
            section.switch_count >= 0,
            all(0.0 <= value <= 1.0 for value in section.pov_distribution.values()),
        ]
        if section.pov_distribution:
            checks.append(sum(section.pov_distribution.values()) <= 1.0 + 1e-6)

        for scene in section.scenes:
            checks.append(bool(scene.pov_character.strip()))
            checks.append(0.0 <= scene.confidence <= 1.0)

        for issue in section.issues:
            checks.append(issue.type in _POV_ISSUE_TYPES)
            checks.append(issue.severity in _POV_SEVERITIES)

        return _score(checks)


@dataclass
class ChapterSummarySchemaValidator(Evaluator[Any, AnalysisMetricsResult, dict[str, Any]]):
    """Validate summary length bounds and key-event extraction coverage for ChapterSummaryAgent.

    Not applicable (returns 1.0) when the case ``agent_type`` is not ``summary``.
    When applicable, checks:

    - summary section present
    - summary non-empty (matches the agent's own invariant)
    - at least one non-empty key_point (agent invariant; "key event coverage")
    - every key_point non-empty
    - word_count > 0 and within the sanity upper bound (length bound)
    - word_count consistent with len(summary.split()) when both are set
    """

    def evaluate(self, ctx: EvaluatorContext[Any, AnalysisMetricsResult, dict[str, Any]]) -> float:
        if not ctx.metadata or ctx.metadata.get("agent_type") != "summary":
            return 1.0

        section = ctx.output.summary
        if section is None:
            return 0.0

        non_empty_points = [p for p in section.key_points if p.strip()]
        actual_words = len(section.summary.split())
        checks: list[bool] = [
            bool(section.summary.strip()),
            bool(non_empty_points),
            all(p.strip() for p in section.key_points) if section.key_points else True,
            0 < section.word_count <= _SUMMARY_MAX_WORDS,
            section.word_count == actual_words if section.summary.strip() else True,
        ]

        return _score(checks)
