/**
 * The autosave state the chrome's sync surfaces read (D10) — one owner for
 * the rail foot's dot, the topbar's save chip and the editor foot: one
 * status, three faces, never a disagreement.
 *
 * LIVE (W4 Task 12): the writing workspace's autosave hook writes its state
 * here (`setSaveStatus`); the chrome reads it through `useSaveStatus`. The
 * shell owns the store because the chrome wraps every route — a capability
 * cannot reach up into it (rule 1), so the state crosses the boundary
 * through this shell-level seam, the `noteNovelDeletedElsewhere` precedent
 * in `query.ts`: module state beside the surface that owns it, written by
 * the capability, read by the shell. Task 10's static „Gespeichert" interim
 * ends here.
 *
 * The vocabulary is the hook's own four states. `idle` (nothing typed, or
 * the draft discarded) and `saved` (the last write landed) both rest at the
 * green face — no unsaved words exist to name. `saving` covers the whole
 * engaged window, the debounce and the wire alike (the draft's amber
 * „In Arbeit"); `failed` is the refused write whose body stays in memory.
 * The draft's three states (chrome-rail-topbar tile 3: Gespeichert /
 * Sicherung läuft … / Sicherung fehlgeschlagen) are the faces; their honest
 * sub-labels ride as the surfaces' tooltips. No invented states ship.
 */
import { useSyncExternalStore } from "react";

import type { MessageKey } from "./i18n";

export type SaveStatus = "idle" | "saving" | "saved" | "failed";

/** The one state, module-level beside the chrome that reads it. */
let current: SaveStatus = "idle";
const listeners = new Set<() => void>();

/** The autosave hook's write door: a new state notifies every reader. */
export function setSaveStatus(status: SaveStatus): void {
  if (status === current) return;
  current = status;
  for (const listener of listeners) listener();
}

export function getSaveStatus(): SaveStatus {
  return current;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** The chrome's read: the live state, re-rendering on every write. */
export function useSaveStatus(): SaveStatus {
  return useSyncExternalStore(subscribe, getSaveStatus, getSaveStatus);
}

/**
 * Whether a status means text that exists only in the browser: waiting for
 * its debounce or on the wire (`saving`), or refused (`failed`). Every guard
 * — the leave dialog, the router blocker, the browser's unload prompt — asks
 * this one question, so a fourth caller cannot answer it differently.
 */
export function unsavedStatus(status: SaveStatus): boolean {
  return status === "saving" || status === "failed";
}

/** The tone each face wears — the shell's success/warning/danger tokens. */
export type SaveTone = "success" | "warning" | "danger";

/**
 * The draft's three sync faces (tile 3), one home so the topbar chip and the
 * rail foot cannot drift. `idle` rests at the green face beside `saved`:
 * nothing unsaved stands, so „Gespeichert" is the honest Ruhe state. The
 * note is the round-2 honest sub-label (#884), carried as the surface's
 * tooltip — no storage-technology claim.
 */
export const SAVE_FACES: Record<SaveStatus, { label: MessageKey; note: MessageKey; tone: SaveTone }> = {
  idle: { label: "shell.rail.saved", note: "shell.rail.saved.note", tone: "success" },
  saved: { label: "shell.rail.saved", note: "shell.rail.saved.note", tone: "success" },
  saving: { label: "shell.rail.saving", note: "shell.rail.saving.note", tone: "warning" },
  failed: { label: "shell.rail.failed", note: "shell.rail.failed.note", tone: "danger" },
};

/** The tone's Tailwind faces — literal class names (the compiler scans them
 *  here, one home), so the topbar chip and the rail dot wear the same colour
 *  for the same state. The ring is the rail dot's own halo. */
export const SAVE_TONE_CLASS: Record<SaveTone, { text: string; dot: string; ring: string }> = {
  success: { text: "text-success", dot: "bg-success", ring: "ring-success/15" },
  warning: { text: "text-warning", dot: "bg-warning", ring: "ring-warning/15" },
  danger: { text: "text-danger", dot: "bg-danger", ring: "ring-danger/15" },
};
