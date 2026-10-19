"""Readability analysis helpers — extracted from readability_service.py (RULE-04).

Contains:
- :func:`merge_agent_result`: Pure data transformation that merges
  ``ReadabilityAgentOutput`` (AI sentence analysis) into a deterministic
  ``ReadabilityResult``.
- :func:`build_deps`: Constructs ``ReadabilityDeps`` keeping the agent
  import out of the service module's top level.
- :func:`fetch_kb_prompt_variables`: Canonical KB-context supply (ADR-067)
  for the readability template's ``kb_*`` slots (audit N12).
- :func:`prepare_readability_agent`: Run-limit resolution + model-call
  preparation + agent construction (extracted when the service sat at its
  300-line RULE-04 hard limit; the ``_prepare_agent`` method stays as the
  instance-level seam tests replace).

These were extracted to keep ``readability_service.py`` under the
300-line RULE-04 limit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from narrare_core.analysis.types import ReadabilityResult, SentenceAnalysis
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.kb.context_contracts import KBContextProviderProtocol
    from narrare_core.agents.readability_agent import ReadabilityAgent, ReadabilityDeps
    from narrare_core.llm import ModelRegistry
    from narrare_core.llm._prepared_call import PreparedModelCall
    from narrare_core.llm.model_routing import ResolvedModel
    from narrare_core.llm.run_limits import DefaultRunLimitResolver


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


async def fetch_kb_prompt_variables(
    provider: KBContextProviderProtocol | None,
    novel_id: UUID,
) -> dict[str, str]:
    """KB-context variables for the readability template's ``{{kb_*}}`` slots.

    Canonical KB-context supply (ADR-067) — the same SSOT source the POV
    service wires (audit B07). A ``None`` provider degrades to empty slots
    (RULE-11); the provider itself never raises.

    Audit N12 root cause: without this supply the readability compose
    ALWAYS failed (``PromptVariableError: Missing required prompt variable
    'kb_characters' in analysis/en/readability``) and the AI phase was
    silently skipped — the UI claimed "No problematic sentences
    detected!" for text that was never analysed.

    Args:
        provider: The canonical KB-context provider, or ``None`` (tests,
            degraded wiring) for empty slots.
        novel_id: Novel whose KB entities are rendered.

    Returns:
        ``kb_characters`` / ``kb_locations`` / ``kb_factions`` /
        ``kb_relationships`` ready for ``PromptContext(extra=...)``.
    """
    from narrare.kb.context_contracts import KBContextBundle
    from narrare_core.context._render_options import RenderOptions

    options = RenderOptions(annotate_provenance=True)
    if provider is None:
        kb_bundle = KBContextBundle.empty(options)
    else:
        kb_bundle = await provider.fetch_context(
            novel_id,
            entity_types=["character", "location", "faction"],
            options=options,
        )
    return kb_bundle.to_prompt_variables()


async def prepare_readability_agent(
    model_registry: ModelRegistry,
    run_limit_resolver: DefaultRunLimitResolver,
    system_prompt: str | None,
    resolved_model: ResolvedModel,
) -> tuple[ReadabilityAgent, PreparedModelCall]:
    """Resolve run limits, prepare the model call, construct the agent.

    Extracted from ``ReadabilityService._prepare_agent`` (RULE-04): the
    service sat at its 300-line hard limit, so the body moved here while
    the method stays as the instance-level seam tests replace.

    A fresh agent per call — agents are lightweight wrappers around the
    model. Returns the coherent ``PreparedModelCall`` triple (Task 6a-2
    single assembly point): the agent's ``run`` must receive
    ``prepared.model_settings`` and ``prepared.usage_limits``.

    Args:
        model_registry: LLM model registry for the ``prepare`` assembly point.
        run_limit_resolver: ADR-045 run-limit resolver.
        system_prompt: Composed feature-specific system prompt (Mode 1,
            ADR-048). When ``None`` the agent falls back to Capabilities only.
        resolved_model: Routing-cascade resolution (ADR-086).

    Returns:
        The fresh ``ReadabilityAgent`` plus the coherent
        ``PreparedModelCall`` triple.
    """
    from narrare_core.agents.readability_agent import ReadabilityAgent

    resolved = run_limit_resolver.resolve(
        config=resolved_model.config, budget=None, invocation_id=uuid4()
    )
    prepared = await model_registry.prepare(
        resolved_model.config,
        intent=LLMIntent.ANALYSE,
        usage_limits=resolved.usage_limits,
        api_key=resolved_model.api_key,
        base_url=resolved_model.base_url,
    )
    return ReadabilityAgent(model=prepared.model, system_prompt=system_prompt), prepared
