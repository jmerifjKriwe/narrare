import type { ChangeDetail } from "@/lib/api/coauthor";
import type { AIDiffViewModel } from "../contracts";
import { segmentize } from "../segmentize";

/** Map a Co-Author {@link ChangeDetail} to a text-mode {@link AIDiffViewModel}. */
export function coAuthorChangeAdapter(change: ChangeDetail): AIDiffViewModel {
  return {
    id: change.id,
    mode: "text",
    segments: segmentize(change.original_text, change.revised_text),
    originalFull: change.original_text,
    suggestedFull: change.revised_text,
    label: change.change_type,
    provisional: false,
  };
}
