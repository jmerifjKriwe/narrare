"""PROMPT-INTEGRITY · Prompt content integrity checks (Gate 9).

Detects:
- i18n gaps (EN prompts without DE/FR counterparts)
- Template variables not registered in _USER_CONTENT_VARS
- Variable existence: every {{variable}} in prompts must be registered
- i18n parity: EN prompt files must have DE/FR variants
- Intent consistency: _INTENT_TO_CATEGORY and _INTENT_TO_MODE coverage
- Variable usage: every _SYSTEM_VARS entry used in at least one prompt

Exit code: 0 = all checks pass (approved_exceptions are advisory).
Exit code: 1 = violations found (CI-blocking).
Exit code: 2 = warnings found (advisory, visible in output).

All checks are advisory (approved=True) by default — they flag potential
issues for review, not CI-blocking violations. Use --strict on the CLI
to elevate to CI-blocking.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from scripts.architecture._checkers._check_i18n import (
    check_i18n_parity,
    check_prompt_i18n_completeness,
)
from scripts.architecture._checkers._check_intents import check_intent_consistency
from scripts.architecture._checkers._check_variables import (
    check_template_variables,
    check_variable_registration,
    check_variable_usage,
)

if TYPE_CHECKING:
    from scripts.architecture.types import CheckResult

# ---------------------------------------------------------------------------
# Main entry point — run all prompt integrity checks
# ---------------------------------------------------------------------------


def run_all_checks(result: CheckResult) -> None:
    """Run all prompt integrity checks and populate *result*.

    This is the main entry point callable from check_architecture.py.
    """
    check_prompt_i18n_completeness(result)
    check_template_variables(result)
    check_variable_registration(result)
    check_i18n_parity(result)
    check_intent_consistency(result)
    check_variable_usage(result)
