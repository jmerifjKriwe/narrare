"""Well-known keys for adaptive prompt variables in dynamic_inputs.

Centralised to keep adaptive.py under RULE-04's 150 LOC cap
("modularize, don't compress"). These keys are used by
AdaptiveContextEnricher to write into dynamic_inputs and by
tests to assert presence/absence.

See:
    ADR-069, CONSTRAINTS.md RULE-04.
"""

from __future__ import annotations

#: Formatted preference text from PreferenceProfile (LEARN-001).
USER_PREFERENCES_KEY: str = "user_preferences"

#: Derived hard style constraints (e.g. "avoid passive voice").
STYLE_CONSTRAINTS_KEY: str = "style_constraints"

#: Things the user dislikes (from feedback).
AVOIDANCE_PATTERNS_KEY: str = "avoidance_patterns"

#: Formatted CharacterVoiceProfile text block (ADR-055).
CHARACTER_VOICE_PROFILES_KEY: str = "character_voice_profiles"

#: Internal-only summary for transparency UI / logging (not in templates).
ADAPTIVE_SOURCE_SUMMARY_KEY: str = "__adaptive_source_summary"

#: Internal-only weights snapshot for evidence (not in templates).
ADAPTIVE_WEIGHTS_KEY: str = "__adaptive_weights"
