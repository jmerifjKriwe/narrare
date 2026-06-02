"use client";

/**
 * ExtractionContent — Phase-based content renderer for the extraction panel.
 *
 * Renders the appropriate sub-component based on the current phase.
 * Keeps ExtractionPanel under the 200-line RULE-04 limit.
 */

import type { ExtractionItem } from "@/lib/api/extraction";
import { ExtractionDone } from "./ExtractionDone";
import { ExtractionError } from "./ExtractionError";
import { ExtractionLoading } from "./ExtractionLoading";
import { ExtractionReview } from "./ExtractionReview";

type ExtractionPhase = "loading" | "review" | "applying" | "done" | "error";

interface ExtractionContentProps {
  phase: ExtractionPhase;
  items: ExtractionItem[];
  selectedIndices: Set<number>;
  analysisNotes: string;
  errorMsg: string | null;
  onToggleItem: (idx: number) => void;
  onSelectAll: () => void;
  onSelectNone: () => void;
  onRetry: () => void;
  onCancel?: () => void;
}

export function ExtractionContent({
  phase,
  items,
  selectedIndices,
  analysisNotes,
  errorMsg,
  onToggleItem,
  onSelectAll,
  onSelectNone,
  onRetry,
  onCancel,
}: ExtractionContentProps) {
  if (phase === "loading") {
    return <ExtractionLoading onCancel={onCancel} />;
  }

  if (phase === "applying") {
    return <ExtractionLoading />;
  }

  if (phase === "review") {
    return (
      <ExtractionReview
        items={items}
        selectedIndices={selectedIndices}
        onToggleItem={onToggleItem}
        onSelectAll={onSelectAll}
        onSelectNone={onSelectNone}
        analysisNotes={analysisNotes}
      />
    );
  }

  if (phase === "done") {
    return <ExtractionDone />;
  }

  if (phase === "error" && errorMsg) {
    return <ExtractionError message={errorMsg} onRetry={onRetry} />;
  }

  return null;
}
