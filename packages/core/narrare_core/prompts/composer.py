"""
Prompt Composer — assembles the final prompt for any LLM call.

This is the ONLY place where prompts are assembled.
Services pass a PromptContext; the composer handles everything else.

The meta-prompt is no longer handled here — it is injected via the
NarrareMeta Capability (ADR-026 Phase 3), which is automatically added
to every NarrareAgent by NarrareAgent.__init__.

See CONSTRAINTS.md RULE-02.
See ADR-002 (unified prompt system).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from narrare_core.prompts.routes import resolve_prompt_route
from narrare_core.prompts.variable_engine import prepare_variables_for_template, substitute

if TYPE_CHECKING:
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.memory.protocols import PreferenceProvider
    from narrare_core.prompts.context import PromptContext
    from narrare_core.prompts.registry import PromptRegistry

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ComposedPrompt:
    """The final assembled prompt, ready to send to the LLM."""

    system: str
    user: str
    first_message: str | None = None


class PromptComposer:
    """
    Assembles complete prompts from a PromptContext.

    Injected into every service that makes LLM calls.
    Never instantiated locally inside a service method.

    The meta-prompt is no longer prepended here — it is injected
    automatically via the NarrareMeta Capability on every NarrareAgent.
    """

    def __init__(
        self,
        registry: PromptRegistry,
        *,
        preference_service: PreferenceProvider | None = None,
    ) -> None:
        self._registry = registry
        self._preference_service = preference_service

    async def build(
        self,
        intent: LLMIntent,
        context: PromptContext,
        *,
        db_content: str | None = None,
        user_prompt: str = "",
    ) -> ComposedPrompt:
        """
        Build a complete prompt for the given intent and context.

        Args:
            intent: LLM operation intent — drives prompt category and mode.
            context: All variables for this operation.
            db_content: User's DB template override, if any.
            user_prompt: The user-facing message. If empty, uses First Message
                         from the prompt file.

        Returns:
            ComposedPrompt with system and user prompts ready for the gateway.

        Raises:
            PromptNotFoundError: If no prompt file exists for this intent.
            PromptVariableError: If a required variable is missing from context.
        """
        route = resolve_prompt_route(intent, context.mode)
        category = route.category
        mode = route.mode
        variables = context.as_variables()

        # Auto-resolve preferences if service configured and context has empty preferences
        if (
            self._preference_service is not None
            and not context.user_preferences
            and context.extra.get("user_id")
            and context.extra.get("project_id")
        ):
            from uuid import UUID

            try:
                profile = await self._preference_service.get_preferences(
                    UUID(str(context.extra["user_id"])),
                    UUID(str(context.extra["project_id"])),
                )
                pref_text = profile.to_prompt_text()
                if pref_text:
                    context.user_preferences = pref_text
                    # Refresh variables with updated context
                    variables = context.as_variables()
            except Exception:
                logger.warning("preference_injection_failed", intent=intent.value)

        # Resolve prompt file via cascade
        resolved = await self._registry.resolve(
            category=category,
            language=context.language,
            mode=mode,
            genre=context.genre or None,
            db_content=db_content,
        )

        system_template = resolved.system_prompt

        # Inject name style guidelines if placeholder present.
        # This is explicit variable provisioning, not automatic XML wrapping.
        if "{{culture_guidelines}}" in system_template and context.extra.get("name_style"):
            name_style_content = await self._registry.resolve_name_style(
                category=category,
                language=context.language,
                style_id=str(context.extra["name_style"]),
            )
            if not name_style_content:
                # Freetext fallback: use the raw name_style string
                name_style_content = (
                    f"Generate names fitting the following style: {context.extra['name_style']}"
                )
            variables["culture_guidelines"] = name_style_content
        elif "{{culture_guidelines}}" in system_template:
            variables["culture_guidelines"] = ""

        prompt_id = f"{category}/{context.language}/{mode}"
        variables = prepare_variables_for_template(
            system_template,
            variables,
            optional_variables=route.optional_variables,
            prompt_id=prompt_id,
        )
        system = substitute(system_template, variables, strict=True)

        # Determine user message
        if user_prompt:
            user_variables = prepare_variables_for_template(
                user_prompt,
                variables,
                optional_variables=route.optional_variables,
                prompt_id=prompt_id,
            )
            final_user = substitute(user_prompt, user_variables, strict=True)
        elif resolved.first_message:
            first_message_variables = prepare_variables_for_template(
                resolved.first_message,
                variables,
                optional_variables=route.optional_variables,
                prompt_id=prompt_id,
            )
            final_user = substitute(resolved.first_message, first_message_variables, strict=True)
        else:
            final_user = context.author_instructions or ""

        logger.debug(
            "prompt_composed",
            intent=intent.value,
            category=category,
            mode=mode,
            language=context.language,
            source=resolved.source,
            system_length=len(system),
        )

        return ComposedPrompt(
            system=system,
            user=final_user,
            first_message=resolved.first_message,
        )
