import type { ChangeDetail, TextChange } from "@/lib/api/coauthor";
import { applyChanges, recordFeedback } from "@/lib/api/coauthor";

// ---------------------------------------------------------------------------
// Params
// ---------------------------------------------------------------------------

interface ApplyPartialChangesParams {
  readonly changes: ChangeDetail[];
  readonly acceptance: Record<string, boolean>;
  readonly chapterId: string;
  readonly novelId: string;
  readonly requestId: string;
  readonly selectionText: string;
}

// ---------------------------------------------------------------------------
// Apply partial changes via API (SET-005) + fire-and-forget feedback
// ---------------------------------------------------------------------------

export async function applyPartialChanges({
  changes,
  acceptance,
  chapterId,
  novelId,
  requestId,
  selectionText,
}: ApplyPartialChangesParams): Promise<string> {
  const acceptedChanges: TextChange[] = changes
    .filter((c) => acceptance[c.id] !== false)
    .map((c) => ({ original_text: c.original_text, revised_text: c.revised_text }));
  const rejectedChanges: TextChange[] = changes
    .filter((c) => acceptance[c.id] === false)
    .map((c) => ({ original_text: c.original_text, revised_text: c.revised_text }));

  const result = await applyChanges(chapterId, novelId, {
    request_id: requestId || crypto.randomUUID(),
    original: selectionText,
    accepted: acceptedChanges,
    rejected: rejectedChanges,
  });

  // Fire-and-forget feedback (LEARN-001) — best-effort for preference learning
  const feedback = changes.map((c) => ({
    change_id: c.id,
    action: (acceptance[c.id] !== false ? "accepted" : "rejected") as "accepted" | "rejected",
    focus: c.change_type,
    original: c.original_text,
    revised: acceptance[c.id] !== false ? c.revised_text : "",
  }));
  recordFeedback(chapterId, novelId, {
    request_id: requestId || crypto.randomUUID(),
    feedback,
  }).catch(() => {
    /* silent — feedback is best-effort */
  });

  return result.content;
}
