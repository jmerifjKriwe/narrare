"""CharacterAgeCheck — age consistency at event points.

Detects characters referenced in timeline events who lack a birth date
in character metadata (PLAN-004 Phase 3).

Extracted from ``temporal.py`` to resolve RULE-04 (file-size limit).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Mapping

from narrare_core.analysis.temporal_types import TemporalIssue, TemporalIssueSeverity


class CharacterAgeCheck:
    """Detect age inconsistencies at event points.

    Checks if character ages are plausible at each timeline event
    based on birth_date in character metadata.
    """

    @staticmethod
    def check(
        events: list[dict[str, object]],
        character_ages: Mapping[str, str | None],
    ) -> list[TemporalIssue]:
        """Check for age inconsistencies.

        Args:
            events: List of event dicts with character_refs and timestamp_raw.
            character_ages: Map of character name to age string (or None if
                no birth_date).

        Returns:
            List of age inconsistency issues.
        """
        characters_without_age: set[str] = set()

        for event in events:
            raw_refs = event.get("character_refs", [])
            refs = cast("list[dict[str, object]]", raw_refs) if isinstance(raw_refs, list) else []
            for ref in refs:
                name = str(ref.get("name", ""))
                if name and name not in character_ages:
                    characters_without_age.add(name)

        if not characters_without_age:
            return []

        return [
            TemporalIssue(
                severity=TemporalIssueSeverity.INFO,
                rule_id="character_missing_birth_date",
                event_ids=[],
                description=(
                    f"{len(characters_without_age)} character(s) referenced in "
                    f"events have no birth date: "
                    f"{', '.join(sorted(characters_without_age))}."
                ),
                suggestion=(
                    "Add birth_date to character metadata in the "
                    "Knowledge Base for age consistency checking."
                ),
            )
        ]
