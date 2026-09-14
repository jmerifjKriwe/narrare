"""Invocation runner for the beta-reader eval — the real chain, no API stack.

Spec: ``docs/superpowers/specs/2026-09-14-beta-reader-eval-design.md`` — §4
(D2) chain steps 2-7 and §9 Slice 2. Drives the exact production
composition per ``beta_reader_service.py`` with only the data source swapped
(corpus files instead of DB rows) and the API transport removed:

* **System prompt** — ``PromptComposer(PromptRegistry()).build(
  LLMIntent.BETA_READ, PromptContext(language, mode, project_title=""))``,
  the service's own Mode-1 fallback composition (``_invocation_compose.py``
  fallback; the render-smoke convention,
  ``test_beta_reader_prompt_render.py``).
* **User prompt (Phase 1)** — ``build_budgeted_prompt(deps,
  AnalysisContextAssembler())`` with the assembler's documented default 32k
  budget (ADR-082 Decision 5; known gap: not the model-window-aware cascade
  — immaterial at single-chapter scale, spec §4 step 4).
* **Model** — the service's ``_prepare_model`` replica (ADR-086):
  ``DefaultRunLimitResolver().resolve(...)`` → ``ModelRegistry().prepare(...)``
  with ``intent=LLMIntent.BETA_READ``. Any ``zai_endpoint`` is accepted
  (PO ruling 2026-09-14) and routed production-faithfully: ``coding`` →
  the Z.AI coding URL (the literal production stores, ``setup/service.py``),
  else the provider default general endpoint. Results reflect the model as
  served by the configured endpoint (spec §11-1).
* **Execution** — ``run_phase1`` / ``run_phase2`` from
  ``beta_reader_agent_run.py`` (real RULE-11 error wrapping); temperature is
  pinned into the ``ResolvedModelConfig`` AND merged into the run-time
  ``model_settings`` (spec §4 step 6). One ``prepare`` per phase, faithful
  to the service.

Injectable seam: ``model_factory`` replaces the real prepare path so unit
tests drive the chain with ``TestModel`` (no LLM, spec §6/D8). Dry-run
composes all prompts with **zero** model calls (spec §6/D8). Real runs
refuse e2e_test mode (the provider registry would silently serve
``TestModel``).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

import structlog
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from scripts.evals.beta_reader_scoring import Layer1Report, check_phase1, check_phase2

from narrare.analysis.beta_reader_agent_run import run_phase1, run_phase2
from narrare.analysis.beta_reader_mapper import build_deepdive_prompt
from narrare.analysis.beta_reader_prompt import build_budgeted_prompt
from narrare_core.agents.beta_reader_agent import BetaReaderAgent
from narrare_core.agents.beta_reader_types import (
    BetaReaderDeps,
    BetaReaderPhase1Output,
    BetaReaderPhase2Output,
)
from narrare_core.analysis.assembler import AnalysisContextAssembler
from narrare_core.llm import LLMIntent, ModelRegistry, ResolvedModelConfig
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.settings import get_core_settings

if TYPE_CHECKING:
    from pydantic_ai.settings import ModelSettings
    from scripts.evals.corpus_source import EvalChapter, EvalCorpusManifest

__all__ = [
    "DEFAULT_DEEPDIVE_CATEGORY",
    "DEFAULT_LLM_CONFIG_PATH",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_TEMPERATURE",
    "MODEL_FACTORY",
    "PHASE1_MODE",
    "PHASE2_MODE",
    "BetaReaderEvalRunner",
    "EvalCaseResult",
    "EvalConfigError",
    "EvalLlmConfig",
    "build_case_deps",
    "build_deepdive_deps",
    "compose_system_prompt",
    "load_llm_config",
    "resolve_base_url",
    "with_temperature",
]

logger = structlog.get_logger(__name__)

PHASE1_MODE: str = "beta_reader"
PHASE2_MODE: str = "beta_reader_deepdive"

DEFAULT_TEMPERATURE: float = 0.0
DEFAULT_DEEPDIVE_CATEGORY: str = "plot"
# Raw pin (``_model_config`` sets no token-limit profile) — and pydantic-ai
# counts ``output_tokens_limit`` cumulatively across validation-retry
# attempts (hazard precedent: the extraction preset raises in
# ``token_profiles.py`` PROFILE_OUTPUT_LIMITS). The verbose deep-dive payload
# is ~4k tokens/response, so the previous 4096 suffocated on the first
# retry (observed 2026-09-14: run exit 1 at output_tokens=8000). Production
# BETA_READ is unaffected — the routing resolver seeds the ``long_texts``
# intent-default profile (64000) on every cascade level.
DEFAULT_MAX_TOKENS: int = 16384

#: Benchmark config the instrument reads (spec §3 data dependency — file via
#: path, ``llm`` section only; never imported as code).
DEFAULT_LLM_CONFIG_PATH: Path = (
    Path(__file__).resolve().parents[2] / "benchmark" / "config.local.yaml"
)

#: Seam type: prepares the ADR-086 triple for a pinned model config.
MODEL_FACTORY = Callable[[ResolvedModelConfig], Awaitable[PreparedModelCall]]

#: Z.AI coding-endpoint base URL — the exact literal production stores for
#: ``zai_endpoint="coding"`` (``apps/api/narrare/setup/service.py``), so eval
#: runs are production-faithful (PO ruling 2026-09-14, spec §11-1).
ZAI_CODING_BASE_URL: str = "https://api.z.ai/api/coding/paas/v4"


def resolve_base_url(zai_endpoint: str | None) -> str | None:
    """Production-parity endpoint routing (spec §11-1, PO ruling 2026-09-14).

    ``coding`` → the Z.AI coding URL (a coding-plan key is rejected by the
    general endpoint); everything else → ``None`` (provider default =
    general endpoint).
    """
    if zai_endpoint == "coding":
        return ZAI_CODING_BASE_URL
    return None


class EvalConfigError(ValueError):
    """Raised when the LLM config is unreadable or invalid."""


class EvalLlmConfig(BaseModel):
    """The eval's own typed view of the benchmark config ``llm`` section.

    The api key exists in-process only (spec §6 secret hygiene) and is
    excluded from ``repr`` so it can never leak into logs or traces.
    """

    model_config = ConfigDict(frozen=True)

    provider: str = Field(min_length=1)
    api_key: str = Field(repr=False)
    model: str = Field(min_length=1)
    zai_endpoint: str | None = None


class EvalCaseResult(BaseModel):
    """Full result of one corpus chapter x both phases.

    ``phase1`` / ``phase2`` / ``layer1_*`` are ``None`` on the dry-run path
    (compose only, zero model calls).
    """

    model_config = ConfigDict(frozen=True)

    stem: str
    system_prompt: str
    user_prompt: str
    deepdive_system_prompt: str
    deepdive_user_prompt: str
    deepdive_category: str
    dry_run: bool = False
    call_count: int = Field(ge=0)
    phase1: BetaReaderPhase1Output | None = None
    phase2: BetaReaderPhase2Output | None = None
    layer1_phase1: Layer1Report | None = None
    layer1_phase2: Layer1Report | None = None


def load_llm_config(path: Path | None = None) -> EvalLlmConfig:
    """Load the eval LLM config from the benchmark config's ``llm`` section.

    ``path`` defaults to :data:`DEFAULT_LLM_CONFIG_PATH`. Raises
    :class:`EvalConfigError` on unreadable/invalid YAML or a missing/invalid
    ``llm`` section — never returns a partially validated config.
    """
    config_path = DEFAULT_LLM_CONFIG_PATH if path is None else path
    try:
        loaded: object = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EvalConfigError(f"{config_path}: unreadable or missing ({exc})") from exc
    except yaml.YAMLError as exc:
        raise EvalConfigError(f"{config_path}: invalid YAML ({exc})") from exc
    if not isinstance(loaded, dict):
        raise EvalConfigError(f"{config_path}: must be a YAML mapping")
    section: object = cast("dict[str, Any]", loaded).get("llm")
    if not isinstance(section, dict):
        raise EvalConfigError(f"{config_path}: missing 'llm' section")
    try:
        return EvalLlmConfig.model_validate(section)
    except ValidationError as exc:
        raise EvalConfigError(f"{config_path}: invalid 'llm' section ({exc})") from exc


def build_case_deps(manifest: EvalCorpusManifest, chapter: EvalChapter) -> BetaReaderDeps:
    """Chain step 2 (spec §4): corpus-sourced deps with the production shape.

    Fidelity gaps vs production (documented, spec §4 step 2 / §11-2): no KB
    envelopes (``kb_characters`` / ``kb_locations`` empty per RULE-11), no
    previous-chapter summaries, no focus-category override.
    """
    return BetaReaderDeps(
        chapter_text=chapter.text,
        chapter_titles=[chapter.title or chapter.stem],
        word_count=chapter.word_count,
        genre=manifest.genre,
        language=manifest.language,
        kb_characters="",
        kb_locations="",
        previous_chapter_summaries=[],
        focus_categories=None,
    )


def build_deepdive_deps(
    deps: BetaReaderDeps,
    phase1: BetaReaderPhase1Output,
    category_value: str,
) -> BetaReaderDeps:
    """Chain step 7 (spec §4): deep-dive deps with the live Phase-1 result
    replacing the production cache — same derivation as
    ``beta_reader_context.deep_dive_deps`` (strength titles; feedback
    titles capped at the first 10)."""
    return deps.model_copy(
        update={
            "deepdive_category": category_value,
            "phase1_strengths_summary": "; ".join(item.title for item in phase1.strengths),
            "phase1_feedback_summary": "; ".join(item.title for item in phase1.feedback[:10]),
        }
    )


async def compose_system_prompt(language: str, mode: str) -> ComposedPrompt:
    """Chain step 3 (spec §4): the service's fallback-mode composition.

    ``PromptComposer`` over the bundled registry with the bare invocation
    context (``language`` / ``mode`` / ``project_title=""``) — identical to
    the ``_invocation_compose.py`` fallback the render smoke proved; German
    manifest language falls back de→EN templates (settled convention, PO
    ruling 3).
    """
    composer = PromptComposer(registry=PromptRegistry())
    context = PromptContext(language=language, mode=mode, project_title="")
    return await composer.build(LLMIntent.BETA_READ, context)


def with_temperature(
    model_settings: ModelSettings | None,
    temperature: float,
) -> ModelSettings:
    """Spec §4 step 6: ``{**prepared.model_settings, "temperature": t}``."""
    merged: ModelSettings = {}
    if model_settings is not None:
        merged.update(model_settings)
    merged["temperature"] = temperature
    return merged


async def _prepare_model_replica(
    llm_config: EvalLlmConfig,
    config: ResolvedModelConfig,
) -> PreparedModelCall:
    """Chain step 5 (spec §4): the service's ``_prepare_model`` replica."""
    resolved = DefaultRunLimitResolver().resolve(config=config, budget=None, invocation_id=uuid4())
    return await ModelRegistry().prepare(
        config,
        intent=LLMIntent.BETA_READ,
        usage_limits=resolved.usage_limits,
        api_key=llm_config.api_key,
        base_url=resolve_base_url(llm_config.zai_endpoint),
    )


def _make_default_model_factory(llm_config: EvalLlmConfig) -> MODEL_FACTORY:
    """Bind the real prepare replica to the loaded config (DI seam default)."""

    async def factory(config: ResolvedModelConfig) -> PreparedModelCall:
        return await _prepare_model_replica(llm_config, config)

    return factory


class BetaReaderEvalRunner:
    """Drives the real beta-reader chain over corpus chapters (spec §4 D2).

    Args:
        manifest: Loaded eval corpus (S1 ``load_eval_corpus``).
        llm_config: The benchmark config ``llm`` section view (any
            ``zai_endpoint`` accepted — PO ruling 2026-09-14, spec §11-1).
        temperature: CLI-pinned temperature (default 0.0, spec §6/D8).
        deepdive_category: Phase-2 deep-dive category (default ``plot``).
        model_factory: Injectable prepare seam for TestModel tests; the
            default is the real ``_prepare_model`` replica.
    """

    def __init__(
        self,
        *,
        manifest: EvalCorpusManifest,
        llm_config: EvalLlmConfig,
        temperature: float = DEFAULT_TEMPERATURE,
        deepdive_category: str = DEFAULT_DEEPDIVE_CATEGORY,
        model_factory: MODEL_FACTORY | None = None,
    ) -> None:
        self._manifest = manifest
        self._llm_config = llm_config
        self._temperature = temperature
        self._deepdive_category = deepdive_category
        self._assembler = AnalysisContextAssembler()
        self._model_factory: MODEL_FACTORY = (
            model_factory if model_factory is not None else _make_default_model_factory(llm_config)
        )

    async def run_case(self, chapter: EvalChapter, *, dry_run: bool = False) -> EvalCaseResult:
        """Run both phases for one corpus chapter (or compose only, dry-run).

        Raises:
            AnalysisError: Agent execution failed (wrapped by the real
                ``run_phase1`` / ``run_phase2`` helpers — RULE-11, never
                silent). Any other harness failure (composition, budget
                assembly) propagates loudly for the CLI's exit-1 mapping.
        """
        logger.info(
            "eval_case_start",
            stem=chapter.stem,
            dry_run=dry_run,
            deepdive_category=self._deepdive_category,
        )
        deps = build_case_deps(self._manifest, chapter)
        phase1_composed = await compose_system_prompt(deps.language, PHASE1_MODE)
        user_prompt = await build_budgeted_prompt(deps, self._assembler)
        deepdive_composed = await compose_system_prompt(deps.language, PHASE2_MODE)

        if dry_run:
            # No Phase-1 result exists in dry-run: the deep-dive prompt shape
            # omits the summary lines (deterministic free capture, spec §6).
            drydive_deps = deps.model_copy(update={"deepdive_category": self._deepdive_category})
            result = EvalCaseResult(
                stem=chapter.stem,
                system_prompt=phase1_composed.system,
                user_prompt=user_prompt,
                deepdive_system_prompt=deepdive_composed.system,
                deepdive_user_prompt=build_deepdive_prompt(drydive_deps),
                deepdive_category=self._deepdive_category,
                dry_run=True,
                call_count=0,
            )
            logger.info("eval_case_dry_run_complete", stem=chapter.stem)
            return result

        if get_core_settings().e2e_test:
            # Fail fast before any model call: under E2E mode the provider
            # registry silently substitutes TestModel for every provider, so
            # a "real" run would record model garbage as a measurement
            # (observed 2026-09-14 with NARRARE_E2E_TEST=1: instant
            # TestModel-generated output, zero network). Dry-run is unaffected.
            raise EvalConfigError(
                "e2e_test mode is enabled (NARRARE_E2E_TEST): the provider "
                "registry serves TestModel — real eval runs require "
                "NARRARE_E2E_TEST=0"
            )

        phase1 = await self._run_phase1(deps, phase1_composed, user_prompt)
        deepdive_deps = build_deepdive_deps(deps, phase1, self._deepdive_category)
        # Artifact capture (spec §4 step 7): run_phase2 builds the SAME
        # string internally via the pure builder — captured here once.
        deepdive_user_prompt = build_deepdive_prompt(deepdive_deps)
        phase2 = await self._run_phase2(deepdive_deps, deepdive_composed)
        layer1_phase1 = check_phase1(phase1, chapter.text)
        layer1_phase2 = check_phase2(phase2, chapter.text)

        result = EvalCaseResult(
            stem=chapter.stem,
            system_prompt=phase1_composed.system,
            user_prompt=user_prompt,
            deepdive_system_prompt=deepdive_composed.system,
            deepdive_user_prompt=deepdive_user_prompt,
            deepdive_category=self._deepdive_category,
            dry_run=False,
            call_count=2,
            phase1=phase1,
            phase2=phase2,
            layer1_phase1=layer1_phase1,
            layer1_phase2=layer1_phase2,
        )
        logger.info(
            "eval_case_complete",
            stem=chapter.stem,
            layer1_phase1_passed=layer1_phase1.passed,
            layer1_phase2_passed=layer1_phase2.passed,
        )
        return result

    def _model_config(self) -> ResolvedModelConfig:
        """Chain step 5 (spec §4): pinned config — CLI temperature (default
        0.0), ``DEFAULT_MAX_TOKENS`` raw output tokens, no streaming."""
        return ResolvedModelConfig(
            provider_name=self._llm_config.provider,
            model_id=self._llm_config.model,
            temperature=self._temperature,
            max_tokens=DEFAULT_MAX_TOKENS,
            streams=False,
        )

    async def _run_phase1(
        self,
        deps: BetaReaderDeps,
        composed: ComposedPrompt,
        user_prompt: str,
    ) -> BetaReaderPhase1Output:
        """Chain step 6 (spec §4): prepare → agent → run_phase1."""
        prepared = await self._model_factory(self._model_config())
        agent = BetaReaderAgent(model=prepared.model, system_prompt=composed.system)
        return await run_phase1(
            agent,
            user_prompt,
            deps,
            model_settings=with_temperature(prepared.model_settings, self._temperature),
            usage_limits=prepared.usage_limits,
        )

    async def _run_phase2(
        self,
        deps: BetaReaderDeps,
        composed: ComposedPrompt,
    ) -> BetaReaderPhase2Output:
        """Chain step 7 (spec §4): prepare → agent → run_phase2."""
        prepared = await self._model_factory(self._model_config())
        agent = BetaReaderAgent(model=prepared.model, system_prompt=composed.system)
        return await run_phase2(
            agent,
            deps,
            prepared.model,
            model_settings=with_temperature(prepared.model_settings, self._temperature),
            usage_limits=prepared.usage_limits,
        )
