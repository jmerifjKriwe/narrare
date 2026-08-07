"""DialogueCoachAgent — NarrareAgent for dialogue analysis + improvement (ASSIST-004).

The pilot consumer of AdaptiveContext (ADR-069). A single LLM call analyses
a user-selected dialogue passage and (in improve mode) proposes targeted
rewrites. The agent produces :class:`DialogueCoachOutput` — a wrapper with
an ``issues`` list + ``adaptive_summary`` transparency field.

Prompt loading (RULE-02b): the governed ``ai_assist/en/dialogue_coach/system.md``
template IS the system prompt. It is resolved Mode 1 by the Layer-3 service
via :class:`~narrare_core.prompts.composer.PromptComposer` and passed to
this agent's constructor as ``system_prompt``. The agent itself contains
NO inline system prompt — it never builds prompts with f-strings (RULE-02).

ADR-055/057 boundary: the agent receives the descriptive
``voice_profiles_text`` via :class:`DialogueCoachDeps`; it NEVER sees
numeric ``voice_metrics``. The Deps class is structurally asserted to
have no metrics field (Task 10 test).

Usage::

    model = await registry.get_model(config)
    agent = DialogueCoachAgent(
        model=model,
        system_prompt=resolved_template_system,  # from PromptComposer Mode 1
    )
    deps = DialogueCoachDeps(
        text_to_analyze='"Hello," she said.',
        mode="improve",
        characters=["Alice"],
        project_title="My Novel",
        genre="Fantasy",
        writing_language="en",
    )
    result = await agent.run(prompt=composed.user or "Analyse this.", deps=deps)
    for issue in result.issues:
        print(issue.issue_type, issue.severity, issue.original_quote)

See Also
--------
ADR-069 — Adaptive Context + Dialogue Coach Vertical.
ADR-054 — Mode-1 PromptComposer mandate.
ADR-055/057 — voice_metrics boundary.
ADR-035 — Agent output validation.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError
from pydantic_ai import RunContext  # noqa: TC002 — pydantic-ai introspects signatures at runtime

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.dialogue_coach_types import (
    DialogueAlternative,
    DialogueCoachDeps,
    DialogueCoachOutput,
    DialogueIssue,
)


class DialogueCoachAgent(NarrareAgent[DialogueCoachDeps, DialogueCoachOutput]):
    """Agent for dialogue analysis + improvement.

    Takes a user-selected dialogue passage + canonical speaker roster +
    mode ("analyze" | "improve") and produces a structured
    :class:`DialogueCoachOutput` — issues with severity, speaker
    attribution, and (in improve mode) alternative rewrites.

    The mode + speaker roster + passage flow as runtime content in the
    agent run prompt (user channel, RULE-02a category 3); the governed
    system prompt flows through PromptComposer (Mode 1, ADR-054).
    """

    def __init__(self, model: Any, system_prompt: str | None = None) -> None:
        super().__init__(
            model=model,
            deps_type=DialogueCoachDeps,
            output_type=[self._process_output, DialogueCoachOutput],
            system_prompt=system_prompt,
        )

    async def _process_output(
        self,
        ctx: RunContext[DialogueCoachDeps],
        issues: list[dict[str, Any]] | None = None,
        adaptive_summary: str = "",
    ) -> DialogueCoachOutput:
        """Output Function — structures the LLM response.

        Parses the raw JSON response into the typed ``DialogueCoachOutput``.
        During streaming (``ctx.partial_output``) returns a minimal empty result.

        Malformed issue entries (missing required keys, validation failures)
        are silently dropped — never crash the agent.
        """
        if ctx.partial_output:
            return DialogueCoachOutput()

        parsed_issues: list[DialogueIssue] = []
        for raw in issues or []:
            try:
                alts_raw = raw.get("alternatives")
                alternatives: list[DialogueAlternative] | None = None
                if alts_raw is not None:
                    alternatives = [DialogueAlternative(**alt) for alt in alts_raw]
                parsed_issues.append(
                    DialogueIssue(
                        issue_type=raw["issue_type"],
                        speaker=raw.get("speaker", ""),
                        original_quote=raw["original_quote"],
                        diagnosis=raw["diagnosis"],
                        severity=raw.get("severity", "low"),
                        alternatives=alternatives,
                    )
                )
            except KeyError, TypeError, ValueError, ValidationError:
                # Skip malformed issue entries — never crash the agent.
                # ValidationError covers empty original_quote/diagnosis
                # (min_length=1) and invalid Literal enum values.
                continue

        return DialogueCoachOutput(
            issues=parsed_issues,
            adaptive_summary=adaptive_summary or "",
        )

    async def run(
        self,
        prompt: str,
        deps: DialogueCoachDeps,
        **kwargs: Any,
    ) -> DialogueCoachOutput:
        """Execute the dialogue coach agent and return structured output.

        Performs lightweight post-validation: drops any issue whose
        ``original_quote`` is empty after parsing (Quality Rule: every
        issue must point at a verbatim quote). This is a defensive
        guard; the governed template instructs the model accordingly.
        """
        output = await super().run(prompt, deps, **kwargs)
        # Defensive filter — protects against whitespace-only quotes that
        # pass Pydantic's min_length=1 but are semantically empty.
        valid_issues = [i for i in output.issues if i.original_quote.strip()]
        if len(valid_issues) != len(output.issues):
            return output.model_copy(update={"issues": valid_issues})
        return output
