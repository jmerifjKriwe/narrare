"""DurationImpossibilityCheck — impossible durations / event sequences.

Detects temporal impossibilities in timeline events:

1. **Same-character location conflict** — A character appears in two
   events with the same ``temporal_order`` but different
   ``location_ref`` values.  (WARNING)

2. **Death before birth** — A death event has a *lower*
   ``temporal_order`` than a birth event for the same character. (ERROR)

3. **Impossibly fast travel** — The same character appears in events
   with consecutive ``temporal_order`` values but the ``location_ref``
   differs (no gap for travel).  (INFO)

Extracted from ``temporal.py`` to resolve RULE-04 (file-size limit).
"""

from __future__ import annotations

from typing import cast

from narrare_core.analysis.temporal_types import TemporalIssue, TemporalIssueSeverity


class DurationImpossibilityCheck:
    """Detect impossible durations / impossible event sequences.

    .. note::

       The checks use ``.get()`` for all extended keys
       (``location_ref``, ``event_type``) so they degrade gracefully when
       those fields are not included in the dict — for example when called
       from a service whose ``_events_to_dicts()`` has not yet been updated.
    """

    @staticmethod
    def check(events: list[dict[str, object]]) -> list[TemporalIssue]:
        """Check for duration impossibilities.

        Args:
            events: List of event dicts that may include keys: id,
                event_name, temporal_order, timestamp_raw,
                character_refs (list of {"id", "name"}), location_ref
                ({"id", "name"}), event_type.

        Returns:
            List of duration impossibility issues.
        """
        issues: list[TemporalIssue] = []
        if not events:
            return issues

        # Only events with a temporal_order can participate in these checks
        ordered = [e for e in events if e.get("temporal_order") is not None]

        issues.extend(DurationImpossibilityCheck._same_char_location(ordered))
        issues.extend(DurationImpossibilityCheck._death_before_birth(events))
        issues.extend(DurationImpossibilityCheck._fast_travel(ordered))

        return issues

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _same_char_location(events: list[dict[str, object]]) -> list[TemporalIssue]:
        """Check 1: Same character, same temporal_order, != location."""
        issues: list[TemporalIssue] = []

        # Group by temporal_order
        by_order: dict[int, list[dict[str, object]]] = {}
        for e in events:
            order = e.get("temporal_order")
            if order is not None:
                key = int(order)  # type: ignore[arg-type]
                by_order.setdefault(key, []).append(e)

        for order, group in by_order.items():
            if len(group) < 2:
                continue

            # char_name → (location_name, event_id)
            seen: dict[str, tuple[str | None, str]] = {}

            for e in group:
                raw_loc = cast("dict[str, object] | None", e.get("location_ref"))
                loc_name: str | None = str(raw_loc.get("name", "")) if raw_loc is not None else None
                eid = str(e.get("id", ""))

                refs = cast("list[dict[str, object]]", e.get("character_refs", []))

                for ref in refs:
                    name = str(ref.get("name", ""))
                    if not name:
                        continue

                    if name in seen:
                        prev_loc, prev_id = seen[name]
                        if loc_name and prev_loc and loc_name != prev_loc:
                            issues.append(
                                TemporalIssue(
                                    severity=TemporalIssueSeverity.WARNING,
                                    rule_id="same_character_different_location",
                                    event_ids=[prev_id, eid],
                                    description=(
                                        f"'{name}' appears at '{prev_loc}' at "
                                        f"temporal_order={order}, but also at "
                                        f"'{loc_name}' in another event at the "
                                        f"same temporal_order."
                                    ),
                                    suggestion=(
                                        "Give the two events different "
                                        "temporal_order values or add a travel "
                                        "event."
                                    ),
                                )
                            )
                    else:
                        seen[name] = (loc_name, eid)

        return issues

    @staticmethod
    def _death_before_birth(events: list[dict[str, object]]) -> list[TemporalIssue]:
        """Check 2: Death before birth."""
        issues: list[TemporalIssue] = []

        # Collect birth / death events per character
        births: dict[str, list[dict[str, object]]] = {}
        deaths: dict[str, list[dict[str, object]]] = {}

        for e in events:
            etype = str(e.get("event_type", ""))
            if etype not in ("birth", "death"):
                continue

            raw_refs = e.get("character_refs", [])
            refs = cast("list[dict[str, object]]", raw_refs if isinstance(raw_refs, list) else [])
            for ref in refs:
                name = str(ref.get("name", ""))
                if not name:
                    continue
                (births if etype == "birth" else deaths).setdefault(name, []).append(e)

        for char_name, d_events in deaths.items():
            b_events = births.get(char_name, [])
            if not b_events:
                continue

            for d in d_events:
                d_order = d.get("temporal_order")
                if d_order is None:
                    continue
                d_order = int(d_order)  # type: ignore[arg-type]

                for b in b_events:
                    b_order = b.get("temporal_order")
                    if b_order is None:
                        continue
                    b_order = int(b_order)  # type: ignore[arg-type]

                    if d_order < b_order:
                        issues.append(
                            TemporalIssue(
                                severity=TemporalIssueSeverity.ERROR,
                                rule_id="death_before_birth",
                                event_ids=[
                                    str(d.get("id", "")),
                                    str(b.get("id", "")),
                                ],
                                description=(
                                    f"'{char_name}' has a death event at "
                                    f"temporal_order={d_order} but a birth "
                                    f"event at temporal_order={b_order}. "
                                    f"Birth must precede death."
                                ),
                                suggestion=(
                                    "Reorder events so the birth occurs before "
                                    "the death, or fix the temporal_order values."
                                ),
                            )
                        )

        return issues

    @staticmethod
    def _fast_travel(events: list[dict[str, object]]) -> list[TemporalIssue]:
        """Check 4: Consecutive events, different location, no gap."""
        issues: list[TemporalIssue] = []

        # Sort globally by temporal_order
        sorted_events = sorted(
            events,
            key=lambda e: int(e["temporal_order"]),  # type: ignore[arg-type]
        )

        # Group by character — preserve global order
        char_events: dict[str, list[dict[str, object]]] = {}
        for e in sorted_events:
            refs = cast("list[dict[str, object]]", e.get("character_refs", []))
            for ref in refs:
                name = str(ref.get("name", ""))
                if not name:
                    continue
                char_events.setdefault(name, []).append(e)

        for char_name, evts in char_events.items():
            for i in range(len(evts) - 1):
                a, b = evts[i], evts[i + 1]

                order_a = int(a["temporal_order"])  # type: ignore[arg-type]
                order_b = int(b["temporal_order"])  # type: ignore[arg-type]

                # Only flag when consecutive (gap of 1)
                if order_b - order_a != 1:
                    continue

                raw_loc_a = cast("dict[str, object] | None", a.get("location_ref"))
                raw_loc_b = cast("dict[str, object] | None", b.get("location_ref"))

                loc_a: str | None = (
                    str(raw_loc_a.get("name", "")) if raw_loc_a is not None else None
                )
                loc_b: str | None = (
                    str(raw_loc_b.get("name", "")) if raw_loc_b is not None else None
                )

                if loc_a and loc_b and loc_a != loc_b:
                    issues.append(
                        TemporalIssue(
                            severity=TemporalIssueSeverity.INFO,
                            rule_id="impossibly_fast_travel",
                            event_ids=[
                                str(a.get("id", "")),
                                str(b.get("id", "")),
                            ],
                            description=(
                                f"'{char_name}' appears at '{loc_a}' "
                                f"(order={order_a}) then at '{loc_b}' "
                                f"(order={order_b}) with no gap for travel."
                            ),
                            suggestion=(
                                f"Add a travel event between '{loc_a}' and "
                                f"'{loc_b}', or increase the temporal_order "
                                f"gap to account for travel time."
                            ),
                        )
                    )

        return issues
