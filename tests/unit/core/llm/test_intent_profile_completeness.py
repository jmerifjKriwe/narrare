"""CI gate: every routeable LLMIntent must have an explicit output token profile.

Prevents FIND-004 regression — new intents without profiles silently fall back
to max_tokens defaults which may be too small for long-form output.

This is a dedicated regression-prevention gate. Related coverage exists in
``test_intent_profiles.py`` and ``test_intents.py``, but this module
consolidates the completeness checks into a single, clear CI barrier with
actionable error messages.
"""

from __future__ import annotations

import warnings

from narrare_core.llm.intent_categories import (
    _INTENT_PROFILE_DEFAULTS,
    INTENT_CATEGORY_MAP,
)
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_config import PROFILE_OUTPUT_LIMITS

# Intents excluded from profile requirements (not routeable through model cascade)
EXCLUDED_INTENTS: set[LLMIntent] = {LLMIntent.EMBED}


class TestIntentProfileCompleteness:
    """CI gate ensuring every routeable intent has an explicit output profile."""

    def test_all_routeable_intents_have_profile(self) -> None:
        """Every routeable intent must have an explicit output token profile.

        This catches the FIND-004 scenario: a new intent is added to
        ``INTENT_CATEGORY_MAP`` but the developer forgets to add a
        corresponding entry in ``_INTENT_PROFILE_DEFAULTS``.
        """
        routeable = set(INTENT_CATEGORY_MAP.keys())
        missing = routeable - set(_INTENT_PROFILE_DEFAULTS.keys()) - EXCLUDED_INTENTS
        assert not missing, (
            f"These routeable intents lack output profiles: {sorted(missing)}. "
            f"Add them to _INTENT_PROFILE_DEFAULTS in intent_categories.py."
        )

    def test_all_profile_values_are_valid(self) -> None:
        """Every profile value must reference a known PROFILE_OUTPUT_LIMITS key.

        Catches typos or stale profile names in ``_INTENT_PROFILE_DEFAULTS``.
        """
        invalid = {
            intent: profile
            for intent, profile in _INTENT_PROFILE_DEFAULTS.items()
            if profile not in PROFILE_OUTPUT_LIMITS
        }
        assert not invalid, (
            f"These intents reference unknown profiles: {invalid}. "
            f"Available profiles: {list(PROFILE_OUTPUT_LIMITS.keys())}"
        )

    def test_no_new_intents_without_registration(self) -> None:
        """Alert when new intents are added to LLMIntent but not registered.

        Uses a warning (not assertion) because unregistered intents may be
        intentionally pending (e.g., work-in-progress features). The warning
        ensures they are not silently forgotten.
        """
        all_intents = set(LLMIntent)
        unregistered = all_intents - set(INTENT_CATEGORY_MAP.keys()) - EXCLUDED_INTENTS
        if unregistered:
            warnings.warn(
                f"New intents without category mapping: {sorted(unregistered)}. "
                f"Register them in INTENT_CATEGORY_MAP and _INTENT_PROFILE_DEFAULTS.",
                stacklevel=2,
            )
