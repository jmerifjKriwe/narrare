"use client";

/**
 * ScratchpadPaneMode — the /scratchpad right-pane state decision
 * (final-review blocker fix for NOTES-001), extracted from
 * ScratchpadWorkspace (RULE-04).
 *
 * Honesty rules implemented by resolveScratchpadPaneMode:
 * - The capture card ("Nothing captured yet") reflects note EXISTENCE as
 *   reported by an UNFILTERED probe query — never the filtered list. A
 *   filter matching zero notes must show the quiet select prompt while the
 *   rail honestly says "no match" (list.noResults), not a contradiction.
 * - While existence is unknown (probe pending/errored) neither claim is
 *   made: the caller renders nothing instead of flashing either state
 *   across TanStack query-key switches.
 * - With any filter active the pane stays quiet even at zero notes.
 *
 * ScratchpadSelectPrompt is the quiet "notes exist, none selected" pane
 * extracted alongside so the orchestrator stays a pure wiring module.
 */

import { useTranslations } from "next-intl";
import type { NoteFilters } from "./NoteFilterBar";

export type ScratchpadPaneMode =
  /** Existence not yet known — render neither pane (no flash). */
  | "unknown"
  /** Quiet prompt — notes exist, or a filter/search is active. */
  | "select-prompt"
  /** First-capture card — provably zero notes and nothing filtered. */
  | "capture-card";

/** Structural slice of the unfiltered `useNotes({ limit: 1 })` probe. */
export interface ExistenceProbeLike {
  readonly isSuccess: boolean;
  readonly data: readonly unknown[] | undefined;
}

export function resolveScratchpadPaneMode(
  probe: ExistenceProbeLike,
  filters: NoteFilters,
): ScratchpadPaneMode {
  if (!probe.isSuccess) return "unknown";
  const notesExist = (probe.data?.length ?? 0) > 0;
  const filtersActive =
    filters.q !== "" || filters.note_type !== "" || filters.tag !== "" || filters.scope !== null;
  return notesExist || filtersActive ? "select-prompt" : "capture-card";
}

export function ScratchpadSelectPrompt() {
  const t = useTranslations("notes");
  return (
    <p
      data-testid="scratchpad-select-prompt"
      className="flex h-full items-center justify-center p-6 text-sm italic text-muted-foreground"
    >
      {t("empty.selectPrompt")}
    </p>
  );
}
