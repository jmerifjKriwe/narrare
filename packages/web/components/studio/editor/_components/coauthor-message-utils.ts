import type { ChangeDetail } from "@/lib/api/coauthor";

import type { CoAuthorPhase } from "./coauthor-styles";

// ---------------------------------------------------------------------------
// Acceptance helpers
// ---------------------------------------------------------------------------

export const createAcceptanceMap = (
  changes: readonly ChangeDetail[],
  accepted: boolean,
): Record<string, boolean> => {
  const result: Record<string, boolean> = {};
  changes.forEach((change) => {
    result[change.id] = accepted;
  });
  return result;
};

export const allChangesAccepted = (
  changes: readonly ChangeDetail[],
  acceptance: Readonly<Record<string, boolean>>,
): boolean => changes.length === 0 || changes.every((change) => acceptance[change.id] !== false);

// ---------------------------------------------------------------------------
// Presentation helpers
// ---------------------------------------------------------------------------

export const getCoAuthorPhaseLabel = (
  phase: CoAuthorPhase,
  t: (key: string) => string,
): string | null => {
  if (phase === "streaming") return `· ${t("coAuthor.streaming")}`;
  if (phase === "review") return `· ${t("coAuthor.reviewPhase")}`;
  return null;
};
