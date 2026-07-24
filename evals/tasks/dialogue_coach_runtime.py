"""Runtime task for the ``dialogue_coach`` suite — RULE-18b behavioural evidence.

Runs the real ``DialogueCoachAgent`` (via ``ModelRegistry``) twice on the
same dialogue passage:

- **High fidelity** (``voice_fidelity=1.0``): the full descriptive voice
  profiles text is composed into the governed system prompt. The LLM has
  a strong voice reference and detects ``voice_mismatch`` issues.
- **Low fidelity** (``voice_fidelity=0.1``): the voice profiles text is
  suppressed (empty string in the prompt). The LLM has no voice reference
  and detects fewer or zero ``voice_mismatch`` issues.

This is where the REAL RULE-18b evidence is collected — the smoke task
verifies structure (TestModel); this task proves behaviour (real LLM).

Prompt composition follows RULE-02b: the governed ``dialogue_coach``
template is resolved via ``PromptComposer.build()`` (Mode 1, Core-only —
no apps/api InvocationPipeline dependency). The ``character_voice_profiles``
template variable is the weight-gating mechanism: populated for high
fidelity, empty for low fidelity.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from evals.models_dialogue_coach import (
    HIGH_FIDELITY_WEIGHT,
    LOW_FIDELITY_WEIGHT,
    DialogueCoachEvalInput,
    DialogueCoachEvalResult,
    DialogueCoachWeightResult,
)

if TYPE_CHECKING:
    from narrare_core.llm import ResolvedModelConfig


def _build_prompt_context(
    inputs: DialogueCoachEvalInput,
    *,
    voice_profiles_text: str,
) -> Any:
    """Build a PromptContext for the dialogue_coach template (Mode 1).

    The ``character_voice_profiles`` extra variable is the weight-gating
    mechanism: populated for high fidelity, empty for low fidelity.
    """

    from narrare_core.prompts.context import PromptContext

    return PromptContext(
        language=inputs.language,
        writing_language=inputs.language,
        project_title=inputs.project_title,
        genre=inputs.genre,
        mode="dialogue_coach",
        extra={
            "mode": "analyze",
            "characters": ", ".join(inputs.characters) if inputs.characters else "",
            "text_to_analyze": inputs.dialogue_passage,
            "character_voice_profiles": voice_profiles_text,
            "user_preferences": "",
            "style_constraints": "",
            "avoidance_patterns": "",
        },
    )


async def dialogue_coach_task(
    inputs: object,
    *,
    config: ResolvedModelConfig,
    api_key: str | None = None,
    base_url: str | None = None,
) -> object:
    """Run the dialogue-coach runtime task (real LLM, RULE-18b evidence)."""

    return await dialogue_coach(
        DialogueCoachEvalInput.model_validate(inputs),
        config=config,
        api_key=api_key,
        base_url=base_url,
    )


async def dialogue_coach(
    inputs: DialogueCoachEvalInput,
    *,
    config: ResolvedModelConfig,
    api_key: str | None = None,
    base_url: str | None = None,
) -> DialogueCoachEvalResult:
    """Run DialogueCoachAgent twice with different voice_fidelity weights.

    Composes the governed system prompt via ``PromptComposer.build()``
    (Mode 1, Core-only). The high-fidelity run includes the full voice
    profiles text; the low-fidelity run suppresses it. A real LLM responds
    to the prompt difference and produces different issue counts.
    """

    from narrare_core.agents.dialogue_coach_agent import DialogueCoachAgent
    from narrare_core.agents.dialogue_coach_types import DialogueCoachDeps
    from narrare_core.llm import LLMIntent, ModelRegistry
    from narrare_core.prompts import PromptComposer
    from narrare_core.prompts.registry import PromptRegistry

    registry = PromptRegistry()
    composer = PromptComposer(registry=registry)
    model_registry = ModelRegistry()

    # ------------------------------------------------------------------
    # High-fidelity run: voice profiles included.
    # ------------------------------------------------------------------
    high_ctx = _build_prompt_context(inputs, voice_profiles_text=inputs.voice_profiles_text)
    high_prompt = await composer.build(LLMIntent.DIALOGUE_COACH, high_ctx)
    high_model = await model_registry.get_model(config, api_key=api_key, base_url=base_url)
    high_agent = DialogueCoachAgent(model=high_model, system_prompt=high_prompt.system)
    high_deps = DialogueCoachDeps(
        text_to_analyze=inputs.dialogue_passage,
        mode="analyze",
        characters=inputs.characters,
        project_title=inputs.project_title,
        genre=inputs.genre,
        writing_language=inputs.language,
        voice_profiles_text=inputs.voice_profiles_text,
    )
    high_output = await high_agent.run(
        prompt=high_prompt.user or "Analyse this dialogue.", deps=high_deps
    )
    high_vm_count = sum(1 for i in high_output.issues if i.issue_type == "voice_mismatch")

    # ------------------------------------------------------------------
    # Low-fidelity run: voice profiles suppressed.
    # ------------------------------------------------------------------
    low_ctx = _build_prompt_context(inputs, voice_profiles_text="")
    low_prompt = await composer.build(LLMIntent.DIALOGUE_COACH, low_ctx)
    low_model = await model_registry.get_model(config, api_key=api_key, base_url=base_url)
    low_agent = DialogueCoachAgent(model=low_model, system_prompt=low_prompt.system)
    low_deps = DialogueCoachDeps(
        text_to_analyze=inputs.dialogue_passage,
        mode="analyze",
        characters=inputs.characters,
        project_title=inputs.project_title,
        genre=inputs.genre,
        writing_language=inputs.language,
        voice_profiles_text="",  # suppressed — low fidelity
    )
    low_output = await low_agent.run(
        prompt=low_prompt.user or "Analyse this dialogue.", deps=low_deps
    )
    low_vm_count = sum(1 for i in low_output.issues if i.issue_type == "voice_mismatch")

    weight_effect = high_vm_count != low_vm_count

    return DialogueCoachEvalResult(
        high_fidelity=DialogueCoachWeightResult(
            voice_fidelity=HIGH_FIDELITY_WEIGHT,
            voice_profiles_included=True,
            voice_mismatch_count=high_vm_count,
            total_issue_count=len(high_output.issues),
        ),
        low_fidelity=DialogueCoachWeightResult(
            voice_fidelity=LOW_FIDELITY_WEIGHT,
            voice_profiles_included=False,
            voice_mismatch_count=low_vm_count,
            total_issue_count=len(low_output.issues),
        ),
        weight_effect_observed=weight_effect,
    )
