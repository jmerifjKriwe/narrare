"use client";

import { Check, Loader2, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";

import type { ChangeDetail } from "@/lib/api/coauthor";

import { ChangeReview } from "../ChangeReview";
import { btnPrimary, btnSecondary, btnSm } from "./coauthor-styles";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface CoAuthorReviewPhaseProps {
  readonly changes: ChangeDetail[];
  readonly acceptance: Record<string, boolean>;
  readonly reasoning: string;
  readonly onToggleChange: (id: string) => void;
  readonly onAcceptAll: () => void;
  readonly onRejectAll: () => void;
  readonly onApply: () => void;
  readonly submitting: boolean;
  readonly onClose: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CoAuthorReviewPhase({
  changes,
  acceptance,
  reasoning,
  onToggleChange,
  onAcceptAll,
  onRejectAll,
  onApply,
  submitting,
  onClose,
}: CoAuthorReviewPhaseProps) {
  const t = useTranslations("studio");

  const allAccepted = changes.length > 0 && changes.every((c) => acceptance[c.id] !== false);
  const allRejected = changes.length > 0 && changes.every((c) => acceptance[c.id] === false);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between p-3 rounded-lg bg-primary/5 border border-primary/20">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-primary" />
          <p className="text-sm font-medium">
            {t("coAuthor.improvementsFound", { count: changes.length })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onAcceptAll}
            className={`${btnSm} ${allAccepted ? "bg-primary text-primary-foreground shadow-sm" : "border border-border hover:bg-accent"}`}
          >
            {t("coAuthor.acceptAll")}
          </button>
          <button
            type="button"
            onClick={onRejectAll}
            className={`${btnSm} ${allRejected ? "bg-destructive/10 text-destructive border border-destructive/30" : "border border-border hover:bg-accent"}`}
          >
            {t("coAuthor.rejectAll")}
          </button>
        </div>
      </div>

      {reasoning && (
        <details className="group">
          <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground select-none">
            {t("coAuthor.reasoning")}
          </summary>
          <p className="mt-1.5 text-sm text-muted-foreground bg-muted/30 rounded-lg p-3">
            {reasoning}
          </p>
        </details>
      )}

      <div className="space-y-3 max-h-80 overflow-y-auto">
        {changes.map((c) => (
          <ChangeReview
            key={c.id}
            change={c}
            isAccepted={acceptance[c.id] !== false}
            onToggle={onToggleChange}
          />
        ))}
      </div>

      <div className="flex items-center gap-2 pt-2">
        <button type="button" onClick={onClose} className={`${btnSecondary} flex-1`}>
          {t("coAuthor.cancel")}
        </button>
        <button
          type="button"
          onClick={onApply}
          disabled={submitting}
          className={`${btnPrimary} flex-1 flex items-center justify-center gap-2 disabled:opacity-50`}
        >
          {submitting ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Check className="w-4 h-4" />
          )}
          <span>{allAccepted ? t("coAuthor.acceptAll") : t("coAuthor.applySelected")}</span>
        </button>
      </div>
    </div>
  );
}
