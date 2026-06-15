"""Readability analysis helpers — extracted from readability_service.py (RULE-04).

Contains:
- :func:`merge_agent_result`: Pure data transformation that merges
  ``ReadabilityAgentOutput`` (AI sentence analysis) into a deterministic
  ``ReadabilityResult``.
- :func:`build_deps`: Constructs ``ReadabilityDeps`` keeping the agent
  import out of the service module's top level.

These were extracted to keep ``readability_service.py`` under the
300-line RULE-04 limit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from narrare_core.analysis.types import ReadabilityResult, SentenceAnalysis

if TYPE_CHECKING:
    from narrare_core.agents.readability_agent import ReadabilityDeps


def merge_agent_result(
    formula_result: ReadabilityResult,
    agent_output: object,
) -> ReadabilityResult:
    """Merge AI sentence analyses into the deterministic result.

    Maps ``ReadabilityAgentOutput.problematic_sentences`` to
    ``list[SentenceAnalysis]`` and carries over the
    ``overall_assessment``.

    Args:
        formula_result: Deterministic result from ``FormulaReadabilityAnalyzer``.
        agent_output: ``ReadabilityAgentOutput`` from the AI agent.

    Returns:
        Merged ``ReadabilityResult`` with both metrics and AI analysis.
    """
    from narrare_core.agents.readability_types import ReadabilityAgentOutput

    output = ReadabilityAgentOutput.model_validate(agent_output)

    sentence_analyses: list[SentenceAnalysis] = []
    for ps in output.problematic_sentences:
        raw_issues: Any = ps.get("issues", [])
        if isinstance(raw_issues, list):
            issue_list = cast("list[Any]", raw_issues)
            issue_strs: list[str] = [str(i) for i in issue_list]
        else:
            issue_strs = [str(raw_issues)]

        raw_suggestions: Any = ps.get("suggestions", [])
        suggestion_strs: list[str] = []
        if isinstance(raw_suggestions, list):
            sugg_list = cast("list[Any]", raw_suggestions)
            for s in sugg_list:
                if isinstance(s, dict):
                    s_dict = cast("dict[str, Any]", s)
                    alt: str = str(s_dict.get("alternative", s))
                    suggestion_strs.append(alt)
                else:
                    suggestion_strs.append(str(s))
        else:
            suggestion_strs = [str(raw_suggestions)]

        sentence_analyses.append(
            SentenceAnalysis(
                sentence=str(ps.get("sentence", "")),
                sentence_index=int(ps.get("sentence_index", 0)),
                issues=issue_strs,
                readability_score=float(ps.get("readability_score", 0.5)),
                suggestions=suggestion_strs,
            )
        )

    return ReadabilityResult(
        metrics=formula_result.metrics,
        genre_benchmarks=formula_result.genre_benchmarks,
        sentence_analyses=sentence_analyses,
        overall_assessment=output.overall_assessment or None,
    )


def build_deps(text: str, language: str) -> ReadabilityDeps:
    """Build ``ReadabilityDeps`` — helper to keep import out of module top-level.

    Args:
        text: Chapter content.
        language: Resolved language code.

    Returns:
        A ``ReadabilityDeps`` instance.
    """
    from narrare_core.agents.readability_agent import ReadabilityDeps

    return ReadabilityDeps(text=text, language=language)
