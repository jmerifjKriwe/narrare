"""Runtime variable validator — pre-composition checks.

Validates :class:`PromptInvocationContext` before
:class:`~narrare_core.prompts.composer.PromptComposer` runs. Catches
missing required variables, invalid dynamic inputs, and incomplete
adoption requirements early, preventing wasted LLM calls.

This validator is **synchronous** and never raises — it always returns
a :class:`ValidationResult`.

Implements:
    RuntimeVariableValidator Protocol from contracts.py.

See:
    ADR-038, INFRA-013, CONSTRAINTS.md RULE-03/RULE-06/RULE-09/RULE-11.
"""

from __future__ import annotations

import structlog

from narrare_core.ai_invocation._enums import (
    KBSuggestedRequirement,
    PreferenceRequirement,
    ValidationStatus,
)
from narrare_core.ai_invocation.models import (
    InvocationWarning,
    PromptInvocationContext,
    ValidationResult,
)

logger = structlog.get_logger(__name__)


class RuntimeVariableValidatorImpl:
    """Validates invocation context variables before prompt composition.

    Checks dynamic inputs, adoption policy requirements, and language
    settings. All checks are synchronous pure-data validations — no
    I/O, no external calls.

    Produces errors for conditions that block the invocation and warnings
    for non-blocking concerns. Returns a single :class:`ValidationResult`
    aggregating all findings.
    """

    def validate(self, context: PromptInvocationContext) -> ValidationResult:
        """Validate invocation variables against declared requirements.

        Runs five checks in order:

        1. ``dynamic_inputs`` must be a ``dict``.
        2. If adoption policy requires preferences, ``user_preferences``
           must exist in ``dynamic_inputs`` and be non-empty.
        3. If adoption policy requires KB-suggested, ``kb_suggested``
           must exist in ``dynamic_inputs`` and be non-empty.
        4. ``language`` must be at least 2 characters.
        5. (Warning) ``output_language`` should be set.

        Args:
            context: The invocation context to validate.

        Returns:
            :class:`ValidationResult` with ``PASS`` or ``FAIL`` status
            and any errors or warnings.
        """
        errors: list[str] = []
        warnings: list[InvocationWarning] = []

        # Check 1: dynamic_inputs must be a dict.
        # Pydantic validates this at construction, but the defensive check
        # ensures correctness if PromptInvocationContext is ever constructed
        # without validation (e.g., via __init__ bypass or raw model_copy).
        # The isinstance check is intentionally broad to catch any non-dict.
        if not isinstance(context.dynamic_inputs, dict):  # type: ignore[unreachable]
            errors.append("dynamic_inputs must be a dict")
            logger.debug(
                "runtime_validation_fail",
                check="dynamic_inputs_type",
                actual_type=type(context.dynamic_inputs).__name__,
            )

        # Check 2: preference requirement
        if (
            context.adoption_policy is not None
            and context.adoption_policy.preference_requirement == PreferenceRequirement.REQUIRED
        ):
            prefs = context.dynamic_inputs.get("user_preferences")
            if not prefs:
                errors.append(
                    "Adoption policy requires user_preferences but it is "
                    "missing or empty in dynamic_inputs"
                )
                logger.debug(
                    "runtime_validation_fail",
                    check="preference_requirement",
                    requirement="REQUIRED",
                    has_preferences=bool(prefs),
                )

        # Check 3: KB-suggested requirement
        if (
            context.adoption_policy is not None
            and context.adoption_policy.kb_suggested_requirement == KBSuggestedRequirement.PROVIDED
        ):
            kb = context.dynamic_inputs.get("kb_suggested")
            if not kb:
                errors.append(
                    "Adoption policy requires kb_suggested but it is "
                    "missing or empty in dynamic_inputs"
                )
                logger.debug(
                    "runtime_validation_fail",
                    check="kb_suggested_requirement",
                    requirement="PROVIDED",
                    has_kb_suggested=bool(kb),
                )

        # Check 4: language must be valid
        if len(context.language) < 2:
            errors.append(f"language must be at least 2 characters, got '{context.language}'")
            logger.debug(
                "runtime_validation_fail",
                check="language_length",
                language=context.language,
            )

        # Check 5 (warning): output_language should be set
        if context.output_language is None:
            warnings.append(
                InvocationWarning(
                    code="output_language_unset",
                    message=("output_language not set; model may use unexpected language"),
                    field="output_language",
                )
            )
            logger.debug(
                "runtime_validation_warning",
                check="output_language_unset",
            )

        status = ValidationStatus.PASS if not errors else ValidationStatus.FAIL
        logger.debug(
            "runtime_validation_complete",
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
