"""Final prompt validator — post-composition checks.

Validates the :class:`~narrare_core.prompts.composer.ComposedPrompt` after
composition and before model invocation. Detects unresolved template
variables (``{{...}}``), empty prompts, and unexpected state.

This validator is **synchronous** and never raises — it always returns
a :class:`ValidationResult`.

Implements:
    FinalPromptValidator Protocol from contracts.py.

See:
    ADR-038, INFRA-013, CONSTRAINTS.md RULE-03/RULE-06/RULE-09/RULE-11.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import structlog

from narrare_core.ai_invocation._enums import ValidationStatus
from narrare_core.ai_invocation.models import (
    InvocationWarning,
    PromptInvocationContext,
    ValidationResult,
)

if TYPE_CHECKING:
    from narrare_core.prompts.composer import ComposedPrompt

logger = structlog.get_logger(__name__)

#: Regex to detect unresolved Mustache-style template variables.
_TEMPLATE_VAR_RE: re.Pattern[str] = re.compile(r"\{\{[^}]+\}\}")


class FinalPromptValidatorImpl:
    """Validates composed prompts before the model call.

    Checks for unresolved template variables, empty system prompts, and
    other post-composition concerns. All checks are synchronous pure-data
    validations — no I/O, no external calls.

    This is the **hard block** before model invocation: any unresolved
    ``{{...}}`` patterns indicate a template variable that was not filled,
    which would result in the LLM receiving raw placeholder syntax.
    """

    def validate(
        self,
        prompt: ComposedPrompt,
        context: PromptInvocationContext,
    ) -> ValidationResult:
        """Validate the final composed prompt.

        Runs four checks:

        1. No unresolved ``{{...}}`` variables in system or user prompt.
        2. System prompt must not be empty or whitespace-only.
        3. (Warning) User prompt is empty or whitespace-only.
        4. (Warning) ``first_message`` is set.

        Args:
            prompt: The composed prompt to validate.
            context: The invocation context that produced the prompt.

        Returns:
            :class:`ValidationResult` with ``PASS`` or ``FAIL`` status
            and any errors or warnings.
        """
        errors: list[str] = []
        warnings: list[InvocationWarning] = []

        # Check 1: unresolved template variables
        system_vars = _TEMPLATE_VAR_RE.findall(prompt.system)
        user_vars = _TEMPLATE_VAR_RE.findall(prompt.user)

        if system_vars:
            unique_system = sorted(set(system_vars))
            errors.append(
                f"Unresolved template variables in system prompt: {', '.join(unique_system)}"
            )
            logger.debug(
                "final_validation_fail",
                check="unresolved_vars_system",
                variables=unique_system,
            )

        if user_vars:
            unique_user = sorted(set(user_vars))
            errors.append(f"Unresolved template variables in user prompt: {', '.join(unique_user)}")
            logger.debug(
                "final_validation_fail",
                check="unresolved_vars_user",
                variables=unique_user,
            )

        # Check 2: empty system prompt
        if not prompt.system.strip():
            errors.append("System prompt is empty")
            logger.debug(
                "final_validation_fail",
                check="empty_system_prompt",
            )

        # Check 3 (warning): empty user prompt
        if not prompt.user.strip():
            warnings.append(
                InvocationWarning(
                    code="empty_user_prompt",
                    message="User prompt is empty; model receives no user input",
                    field="user",
                )
            )
            logger.debug(
                "final_validation_warning",
                check="empty_user_prompt",
            )

        # Check 4 (warning): first_message is set
        if prompt.first_message is not None and prompt.first_message.strip():
            warnings.append(
                InvocationWarning(
                    code="first_message_set",
                    message=(
                        "First message is set; verify this is intentional for the invocation mode"
                    ),
                    field="first_message",
                )
            )
            logger.debug(
                "final_validation_warning",
                check="first_message_set",
            )

        status = ValidationStatus.PASS if not errors else ValidationStatus.FAIL
        logger.debug(
            "final_validation_complete",
            status=status.value,
            error_count=len(errors),
            warning_count=len(warnings),
            feature_id=context.feature_id,
        )

        return ValidationResult(
            status=status,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )
