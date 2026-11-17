/**
 * The autosave state the chrome's sync surfaces read (D10) — one owner for
 * the rail foot's dot, the topbar's save chip and, from Task 12, the editor
 * foot: one status, three faces, never a disagreement.
 *
 * INTERIM (W4 Task 10): the scene editor does not exist yet, so nothing is
 * pending and nothing has failed — the honest state is the static "saved".
 * Task 12 wires the real autosave hook here (debounce, flush, leave guard)
 * and the interim ends; the draft's three states (chrome-rail-topbar tile 3:
 * Gespeichert / Sicherung läuft … / Sicherung fehlgeschlagen) are the
 * vocabulary the live hook will speak. No invented states ship before it.
 */
export type SaveStatus = "saved" | "saving" | "failed";

export function useSaveStatus(): SaveStatus {
  return "saved";
}
