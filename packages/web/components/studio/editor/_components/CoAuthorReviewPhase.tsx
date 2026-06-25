"use client";

import { Check, Loader2, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect } from "react";
import { isApplyShortcut } from "@/lib/ai-action-shortcuts";
import type { ChangeDetail } from "@/lib/api/coauthor";
import type { StyleVariant } from "@/lib/api/generation";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";

import { ChangeReview } from "../ChangeReview";
import { CoAuthorStyleVariantSection } from "./CoAuthorStyleVariantSection";
import { btnPrimary, btnSecondary, btnSm } from "./coauthor-styles";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface CoAuthorReviewPhaseProps {
  readonly projectId?: string;
  readonly chapterId?: string | null;
  readonly changes: ChangeDetail[];
  readonly acceptance: Record<string, boolean>;
  readonly reasoning: string;
  readonly onToggleChange: (id: string) => void;
  readonly onAcceptAll: () => void;
  readonly onRejectAll: () => void;
  readonly onApply: () => void;
  readonly submitting: boolean;
  readonly onClose: () => void;
  /** Currently selected style variant (CR-AUFG-07-22 Increment B). */
  readonly styleVariant: StyleVariant | null;
  /** Fire when the writer picks a variant to regenerate the output as. */
  readonly onSelectStyleVariant: (variant: StyleVariant) => void;
  /** Regenerated passage text (empty until the variant stream completes). */
  readonly variantText: string;
  /** True while a style-variant regeneration is streaming. */
  readonly isVariantStreaming: boolean;
  /** Structured error from the last variant stream (null when none). */
  readonly variantError: AIErrorResponse | null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CoAuthorReviewPhase({
  projectId,
  chapterId = null,
  changes,
  acceptance,
  reasoning,
  onToggleChange,
  onAcceptAll,
  onRejectAll,
  onApply,
  submitting,
  onClose,
  styleVariant,
  onSelectStyleVariant,
  variantText,
  isVariantStreaming,
  variantError,
}: CoAuthorReviewPhaseProps) {
  const t = useTranslations("studio");

  const allAccepted = changes.length > 0 && changes.every((c) => acceptance[c.id] !== false);
  const allRejected = changes.length > 0 && changes.every((c) => acceptance[c.id] === false);

  // Keyboard Shortcut: Ctrl/Cmd+Enter applies accepted changes (CR-AUFG-07-13).
  // NOTE: Escape → close is handled by the parent CoAuthorPanel's global Escape
  // handler (which calls handleCancel). Adding a second Escape listener here
  // would cause the handler to fire twice — so only the apply shortcut is local.
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (isApplyShortcut(e) && !submitting) {
        e.preventDefault();
        onApply();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [submitting, onApply]);

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
            {t("aiActions.acceptAll")}
          </button>
          <button
            type="button"
            onClick={onRejectAll}
            className={`${btnSm} ${allRejected ? "bg-destructive/10 text-destructive border border-destructive/30" : "border border-border hover:bg-accent"}`}
          >
            {t("aiActions.rejectAll")}
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
            projectId={projectId}
            chapterId={chapterId}
          />
        ))}
      </div>

      {/* Style-Variant Regeneration on the Co-Author output (CR-AUFG-07-22 Increment B).
          The original output above stays visible and unchanged; the regenerated
          variant is surfaced below for comparison (spec: "original remains
          visible until a variant is accepted"). Lives in its own component per
          RULE-04 (component hard limit). */}
      <CoAuthorStyleVariantSection
        selectedVariant={styleVariant}
        onSelectVariant={onSelectStyleVariant}
        variantText={variantText}
        isVariantStreaming={isVariantStreaming}
        variantError={variantError}
        disabled={submitting}
      />

      <div className="flex items-center gap-2 pt-2">
        <button
          type="button"
          onClick={onClose}
          className={`${btnSecondary} flex-1`}
          data-testid="coauthor-cancel-review"
        >
          {t("coAuthor.cancel")}
        </button>
        <button
          type="button"
          onClick={onApply}
          disabled={submitting}
          title="Ctrl/⌘+Enter"
          className={`${btnPrimary} flex-1 flex items-center justify-center gap-2 disabled:opacity-50`}
        >
          {submitting ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Check className="w-4 h-4" />
          )}
          <span>{allAccepted ? t("aiActions.acceptAll") : t("aiActions.applySelected")}</span>
        </button>
      </div>
    </div>
  );
}
