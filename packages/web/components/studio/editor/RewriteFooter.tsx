"use client";

import { Loader2, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import type { RewriteMode } from "@/lib/api/generation";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RewriteFooterProps {
  readonly mode: RewriteMode;
  readonly customInstructions: string;
  readonly count: number;
  readonly setCount: (count: number) => void;
  readonly isGenerating: boolean;
  readonly onGenerate: () => void;
  readonly onCancel: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Count selector and action buttons for the rewrite modal. */
export function RewriteFooter({
  mode,
  customInstructions,
  count,
  setCount,
  isGenerating,
  onGenerate,
  onCancel,
}: RewriteFooterProps) {
  const t = useTranslations("studio");

  return (
    <div className="p-5 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium">{t("rewrite.count")}</span>
        <div className="flex gap-1">
          {[1, 2, 3].map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setCount(c)}
              className={`w-8 h-8 text-xs font-medium rounded-md border transition-colors ${
                count === c
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border hover:border-primary/50"
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 text-sm border border-border rounded-lg hover:bg-accent transition-colors"
        >
          {t("aiActions.stop")}
        </button>
        <button
          type="button"
          onClick={onGenerate}
          disabled={isGenerating || (mode === "custom" && customInstructions.trim().length === 0)}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {isGenerating ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>{t("rewrite.generating")}</span>
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              <span>{t("rewrite.generate")}</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
