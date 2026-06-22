"use client";

import { Check, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { AIDiffView } from "@/components/shared/ai-diff/AIDiffView";
import { coAuthorChangeAdapter } from "@/lib/ai-diff/adapters/coauthor";
import type { AIDiffState } from "@/lib/ai-diff/contracts";
import type { ChangeDetail } from "@/lib/api/coauthor";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ChangeReviewProps {
  readonly change: ChangeDetail;
  readonly isAccepted: boolean;
  readonly onToggle?: (changeId: string) => void;
  readonly readOnly?: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Co-Author change card (CR-AUFG-07-18).
 *
 * Renders the original→revised diff through the shared {@link AIDiffView}
 * (text mode via {@link coAuthorChangeAdapter}), giving every AI review surface
 * the same accessible `<ins>`/`<del>` vocabulary, state badge, and sr summary.
 *
 * The toggle button's visible text and aria-label both describe the ACTION a
 * click will perform (accept / reject), so sighted and screen-reader users
 * receive consistent information — no hard-coded English (RULE-16).
 */
export function ChangeReview({
  change,
  isAccepted,
  onToggle,
  readOnly = false,
}: ChangeReviewProps) {
  const t = useTranslations("studio");
  const viewModel = coAuthorChangeAdapter(change);
  const state: AIDiffState = isAccepted ? "accepted" : "suggested";

  return (
    <div
      className={`rounded-lg border transition-all ${
        isAccepted ? "border-green-500/50 bg-green-500/5" : "border-border hover:border-primary/30"
      }`}
    >
      {/* Header row: change index + accept/reject toggle */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border/50">
        <span className="text-xs text-muted-foreground">#{change.index + 1}</span>
        {!readOnly && onToggle && (
          <button
            type="button"
            onClick={() => onToggle(change.id)}
            aria-label={isAccepted ? t("aiDiff.rejectChange") : t("aiDiff.acceptChange")}
            className={`flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-md transition-all ${
              isAccepted
                ? "bg-green-500/10 text-green-600 dark:text-green-400 hover:bg-green-500/20"
                : "bg-muted text-muted-foreground hover:bg-accent"
            }`}
          >
            {isAccepted ? (
              <>
                <X className="w-3 h-3" />
                <span>{t("aiActions.reject")}</span>
              </>
            ) : (
              <>
                <Check className="w-3 h-3" />
                <span>{t("aiActions.accept")}</span>
              </>
            )}
          </button>
        )}
      </div>

      {/* Diff content via shared AIDiffView (accessible ins/del + badge) */}
      <div className="px-3 py-2.5">
        <AIDiffView viewModel={viewModel} state={state} />
      </div>
    </div>
  );
}
