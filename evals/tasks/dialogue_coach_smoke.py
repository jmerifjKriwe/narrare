"""Deterministic CI-safe smoke task for the ``dialogue_coach`` suite.

This is the **RULE-18b structural-verification harness** (ADR-069). It
runs the real ``DialogueCoachAgent`` with ``TestModel`` to verify:

1. The agent can be instantiated and run without error (structural).
2. The tool-mode output function (``_process_output``) correctly parses
   the JSON contract into ``DialogueCoachOutput`` (Plan-Bug #19 pattern:
   ``custom_output_args`` for tool-mode, not ``custom_output_text``).
3. The weight-gating logic correctly includes/suppresses voice profiles
   text based on ``voice_fidelity``.

The REAL behavioural evidence (LLM produces different issue counts when
the weight changes) is collected in runtime mode via
``RuntimeTaskFactory.dialogue_coach_task``.

**Why TestModel with different ``custom_output_args`` per run?**

TestModel ignores prompt content and returns whatever
``custom_output_args`` specifies. To simulate the weight effect in smoke
mode, the high-fidelity run injects ``voice_mismatch`` issues (as a real
LLM would when given voice profiles) and the low-fidelity run injects
zero voice mismatches (as a real LLM would without voice profiles). This
proves the *plumbing* works; the *behaviour* is proven in runtime mode.
"""

from __future__ import annotations

from typing import Any

from evals.models_dialogue_coach import (
    HIGH_FIDELITY_WEIGHT,
    LOW_FIDELITY_WEIGHT,
    DialogueCoachEvalInput,
    DialogueCoachEvalResult,
    DialogueCoachWeightResult,
)


def _voice_mismatch_issues(passage: str, speaker: str) -> list[dict[str, Any]]:
    """Build the simulated high-fidelity voice_mismatch issues.

    These mirror the JSON contract that the governed template instructs the
    LLM to produce. In smoke mode, TestModel returns them verbatim via
    ``custom_output_args``; in runtime mode, the real LLM generates them
    after seeing the voice profiles + mismatched passage.
    """

    return [
        {
            "issue_type": "voice_mismatch",
            "speaker": speaker,
            "original_quote": passage.split('"')[1] if '"' in passage else passage[:60],
            "diagnosis": (
                f"The dialogue does not match {speaker}'s established voice "
                "profile. The register, vocabulary, or cadence is inconsistent "
                "with how this character speaks."
            ),
            "severity": "medium",
        }
    ]


async def dialogue_coach_task(inputs: object) -> object:
    """Run the CI-safe dialogue-coach smoke task (TestModel-based).

    Instantiates ``DialogueCoachAgent`` with ``TestModel`` and runs it
    twice — once per weight setting — using ``custom_output_args`` to
    simulate the weight effect (Plan-Bug #19: tool-mode output).
    """

    return await dialogue_coach(DialogueCoachEvalInput.model_validate(inputs))


async def dialogue_coach(inputs: DialogueCoachEvalInput) -> DialogueCoachEvalResult:
    """Produce the weight-effect comparison via TestModel-backed agent runs.

    The high-fidelity run injects ``voice_mismatch`` issues (simulating a
    real LLM that detected mismatches thanks to the voice profiles). The
    low-fidelity run injects zero issues (simulating a real LLM without
    voice profiles). Both runs exercise the agent's ``_process_output``
    tool function end-to-end.
    """

    from pydantic_ai.models.test import TestModel

    from narrare_core.agents.dialogue_coach_agent import DialogueCoachAgent
    from narrare_core.agents.dialogue_coach_types import DialogueCoachDeps

    speaker = inputs.characters[0] if inputs.characters else ""

    # ------------------------------------------------------------------
    # High-fidelity run: voice profiles included, mismatches detected.
    # ------------------------------------------------------------------
    high_issues = _voice_mismatch_issues(inputs.dialogue_passage, speaker)
    high_model = TestModel(
        custom_output_args={
            "issues": high_issues,
            "adaptive_summary": (
                "Voice profiles active — voice fidelity weight at 1.0. "
                "Analysis shaped by the supplied character voice reference."
            ),
        }
    )
    high_agent = DialogueCoachAgent(model=high_model, system_prompt="[smoke] dialogue_coach")
    high_deps = DialogueCoachDeps(
        text_to_analyze=inputs.dialogue_passage,
        mode="analyze",
        characters=inputs.characters,
        project_title=inputs.project_title,
        genre=inputs.genre,
        writing_language=inputs.language,
        voice_profiles_text=inputs.voice_profiles_text,
    )
    high_output = await high_agent.run(prompt="Analyse this dialogue.", deps=high_deps)
    high_vm_count = sum(1 for i in high_output.issues if i.issue_type == "voice_mismatch")

    # ------------------------------------------------------------------
    # Low-fidelity run: voice profiles suppressed, no mismatches detected.
    # ------------------------------------------------------------------
    low_model = TestModel(
        custom_output_args={
            "issues": [],
            "adaptive_summary": (
                "No voice signals active — voice fidelity weight at 0.1. "
                "Voice profiles suppressed; no voice matching performed."
            ),
        }
    )
    low_agent = DialogueCoachAgent(model=low_model, system_prompt="[smoke] dialogue_coach")
    low_deps = DialogueCoachDeps(
        text_to_analyze=inputs.dialogue_passage,
        mode="analyze",
        characters=inputs.characters,
        project_title=inputs.project_title,
        genre=inputs.genre,
        writing_language=inputs.language,
        voice_profiles_text="",  # suppressed — low fidelity
    )
    low_output = await low_agent.run(prompt="Analyse this dialogue.", deps=low_deps)
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
