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

Status: every remaining entry is ``RULE-11`` (legitimately optional). All
``§7 GAP`` entries have been closed (the last two — coreference
``kb_locations``/``kb_factions`` — were wired through the canonical
``KBContextProvider`` in W4a). With §7 stub-gaps at 0 the detector
(:mod:`doc_drift.stub_variable_checks`) is now **CI-blocking** (critical):
any *new* unallowlisted stub fails CI, while the 10 RULE-11 entries stay
absorbed (no finding).

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
    (
        "apps/api/narrare/analysis/voice_drift_prompt.py",
        "kb_characters",
        "RULE-11: optional KB-context var declared explicitly so the "
        "template renders empty rather than crash the variable engine "
        "(per in-code comment).",
    ),
    (
        "apps/api/narrare/analysis/voice_drift_prompt.py",
        "kb_locations",
        "RULE-11: optional KB-context var (see voice_drift_prompt.py comment).",
    ),
    (
        "apps/api/narrare/analysis/voice_drift_prompt.py",
        "kb_factions",
        "RULE-11: optional KB-context var (see voice_drift_prompt.py comment).",
    ),
    # ── analysis/coreference_prompt.py — §7 gaps CLOSED (kb_characters/
    #    kb_locations/kb_factions/kb_relationships now wired through the
    #    canonical KBContextProvider, ADR-067; spread from
    #    ``to_prompt_variables()`` so no literal "" stub remains). No
    #    allowlist entries remain here. ──
    # ── planning/* — §7 gaps CLOSED (entity_events + existing_plot_points
    #    now wired from the injected TimelineEventRepository; rendered via
    #    planning/_event_render.py). No allowlist entries remain here. ──
    # ── writing/* — RULE-11 confirmed-optional ──
    (
        "apps/api/narrare/writing/story_suggest_service.py",
        "chapter_outline",
        "RULE-11: the chapter outline is wired from the OutlineRepository "
        "when a chapter_id is set (§7 closed); empty when no chapter_id is "
        "targeted — story-suggest is a project-level tool and a chapter "
        "need not be selected (confirmed-optional var, declared explicitly "
        "so template substitution always succeeds).",
    ),
)


def allowlist_pairs() -> set[tuple[str, str]]:
    """Return the set of ``(rel_path, var)`` pairs in the ratcheted baseline."""
    return {(rel, var) for rel, var, _reason in STUB_ALLOWLIST}
