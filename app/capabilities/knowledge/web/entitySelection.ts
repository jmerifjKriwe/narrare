import { useEffect } from "react";

/**
 * The `?entity=` selection's one rule, shared by the list and the lens: a
 * param naming an entity the novel does not have is a dead link — no
 * selection, never an error — and the dead value leaves the address with a
 * replace, so the cleanup is not a history step. Waiting for the rows before
 * judging keeps a just-selected address alive: the param is never judged
 * against an answer that has not landed.
 */
export function isDeadEntityParam(
  rows: ReadonlyArray<{ id: string }> | undefined,
  entityParam: string | undefined,
): boolean {
  if (entityParam === undefined || rows === undefined) return false;
  return !rows.some((entity) => entity.id === entityParam);
}

/**
 * The dead-`?entity=` cleanup both views run: the list's own and the lens's
 * mirror for standing alone. One hook, one behaviour, wherever it mounts.
 */
export function useDeadEntityCleanup({
  rows,
  entityParam,
  select,
}: {
  rows: ReadonlyArray<{ id: string }> | undefined;
  entityParam: string | undefined;
  select: (entityId: string | null) => void;
}): void {
  useEffect(() => {
    if (isDeadEntityParam(rows, entityParam)) select(null);
  }, [rows, entityParam, select]);
}
