import { useMemo } from "react";
import type { StepStatus, WritingStep } from "../writing/WritingGraphStatus";

const STEP_ORDER: WritingStep[] = [
  "plan_outline",
  "write_draft",
  "review_draft",
  "revise_draft",
  "finalize",
  "generate_summary",
];

export function useWritingGraphSteps(
  isGenerating: boolean,
  activeChapterId: string | null,
): Array<{ id: WritingStep; status: StepStatus }> {
  return useMemo(() => {
    if (isGenerating && activeChapterId) {
      return STEP_ORDER.map((id, idx) => {
        if (idx < 2) return { id, status: "completed" as const };
        if (idx === 2) return { id, status: "current" as const };
        return { id, status: "pending" as const };
      });
    }

    return STEP_ORDER.map((id) => ({ id, status: "pending" as const }));
  }, [isGenerating, activeChapterId]);
}
