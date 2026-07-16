"""Ratcheted (file, var) allowlist for the §7 stub-variable detector.

This is the §7 work list — see ``stub_variable_checks.py`` for the detector
and the full §7 background. Every current occurrence of the anti-pattern (a
registered prompt variable assigned a literal empty string ``""`` inside a
service-layer ``extra=`` / ``variables=`` dict) is recorded here so the
checker starts from a clean baseline (zero new warnings) and the §7 surface
is bounded.

Each entry is ``(repo-relative POSIX path, registered variable, reason)``.
The reason tags the entry as either:

  * ``RULE-11`` — legitimately empty (graceful-degradation / genuinely
    optional var; the template renders correctly without it), or
  * ``§7 GAP`` — a true stub: an assembler/value source is supposed to be
    wired but is not (tagged for remediation).

How to use the work list:

  * **Close a §7 GAP** — wire the real value source, then remove the entry.
    The checker stays clean and the inventory shrinks.
  * **Confirm a RULE-11 entry** — it stays; the empty is intentional.
  * **Never** delete an entry to silence a new warning without either wiring
    the source or documenting a confirmed-optional reason.

The detector imports :data:`STUB_ALLOWLIST` and :func:`allowlist_pairs` from
here; this module holds only data + the (file, var) lookup, so a growing
work list never pushes the detector past its RULE-04 size limit.

See: .opencode/context/narrare-dev/standards/architectural-discipline.md §7
"""

from __future__ import annotations

# Triage legend:
#   RULE-11  — template renders correctly empty; genuinely optional.
#   §7 GAP   — value source supposed to be wired but is not; close it.
STUB_ALLOWLIST: tuple[tuple[str, str, str], ...] = (
    # ── analysis/* — KB-context vars framed as graceful degradation ──
    (
        "apps/api/narrare/analysis/character_voice_prompt.py",
        "kb_characters",
        "RULE-11: optional KB-context var declared explicitly so the "
        "template renders empty rather than crash the variable engine "
        "(per in-code comment). KB assembler not wired for this path.",
    ),
    (
        "apps/api/narrare/analysis/character_voice_prompt.py",
        "kb_locations",
        "RULE-11: optional KB-context var (see character_voice_prompt.py comment).",
    ),
    (
        "apps/api/narrare/analysis/character_voice_prompt.py",
        "kb_factions",
        "RULE-11: optional KB-context var (see character_voice_prompt.py comment).",
    ),
    (
        "apps/api/narrare/analysis/coreference_prompt.py",
        "kb_locations",
        "§7 GAP: in-code comment admits 'Locations and factions can be "
        "added later' — deferred assembler, not a confirmed-optional var.",
    ),
    (
        "apps/api/narrare/analysis/coreference_prompt.py",
        "kb_factions",
        "§7 GAP: in-code comment admits 'Locations and factions can be "
        "added later' — deferred assembler, not a confirmed-optional var.",
    ),
    (
        "apps/api/narrare/analysis/voice_check_prompt.py",
        "kb_characters",
        "RULE-11: optional KB-context var declared explicitly so the "
        "template renders empty rather than crash the variable engine "
        "(per in-code comment).",
    ),
    (
        "apps/api/narrare/analysis/voice_check_prompt.py",
        "kb_locations",
        "RULE-11: optional KB-context var (see voice_check_prompt.py comment).",
    ),
    (
        "apps/api/narrare/analysis/voice_check_prompt.py",
        "kb_factions",
        "RULE-11: optional KB-context var (see voice_check_prompt.py comment).",
    ),
    # ── planning/* — admitted unwired assemblers (true §7 gaps) ──
    (
        "apps/api/narrare/planning/character_arc_service.py",
        "existing_plot_points",
        "§7 GAP: 'No plot-point assembler wired for this call path yet' (per in-code comment).",
    ),
    (
        "apps/api/narrare/planning/character_arc_service.py",
        "culture_guidelines",
        "§7 GAP: no culture-guidelines assembler wired for this path.",
    ),
    (
        "apps/api/narrare/planning/timeline_analysis_service.py",
        "entity_events",
        "§7 GAP: 'No entity-event source wired yet (see ADR-049 D8 notes)' (per in-code comment).",
    ),
    (
        "apps/api/narrare/planning/timeline_analysis_service.py",
        "kb_characters",
        "§7 GAP: 'No KB assembler wired for this call path yet' "
        "(per in-code comment; only kb_relationships is populated).",
    ),
    (
        "apps/api/narrare/planning/timeline_analysis_service.py",
        "kb_locations",
        "§7 GAP: no KB assembler wired for this call path yet.",
    ),
    (
        "apps/api/narrare/planning/timeline_analysis_service.py",
        "kb_factions",
        "§7 GAP: no KB assembler wired for this call path yet.",
    ),
    (
        "apps/api/narrare/planning/timeline_analysis_service.py",
        "culture_guidelines",
        "§7 GAP: no culture-guidelines assembler wired for this path.",
    ),
    (
        "apps/api/narrare/planning/timeline_extraction_service.py",
        "culture_guidelines",
        "§7 GAP: no culture-guidelines assembler wired for this path.",
    ),
    # ── writing/* — admitted unwired assemblers (true §7 gaps) ──
    (
        "apps/api/narrare/writing/story_suggest_service.py",
        "chapter_outline",
        "§7 GAP: 'No chapter-outline assembler wired for this call path "
        "yet' (per in-code comment).",
    ),
    (
        "apps/api/narrare/writing/story_suggest_service.py",
        "culture_guidelines",
        "§7 GAP: no culture-guidelines assembler wired for this path.",
    ),
)


def allowlist_pairs() -> set[tuple[str, str]]:
    """Return the set of ``(rel_path, var)`` pairs in the ratcheted baseline."""
    return {(rel, var) for rel, var, _reason in STUB_ALLOWLIST}
