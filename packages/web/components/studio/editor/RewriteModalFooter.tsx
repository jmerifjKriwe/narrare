"use client";

/**
 * RewriteModalFooter — Action buttons for RewriteSuggestionModal.
 *
 * Extracted from RewriteSuggestionModal for RULE-04 file size compliance.
 * Shows reject, insert-as-new, new-suggestions, and accept/replace buttons.
 */

import { Check, Plus, RotateCcw, X } from "lucide-react";

type StudioTranslator = (key: string) => string;

interface RewriteModalFooterProps {
  readonly onReject: () => void;
  readonly onInsertAsNew: () => void;
  readonly onNewSuggestions: () => void;
  readonly onAccept: () => void;
  readonly t: StudioTranslator;
}

export function RewriteModalFooter({
  onReject,
  onInsertAsNew,
  onNewSuggestions,
  onAccept,
  t,
}: RewriteModalFooterProps) {
  return (
    <div className="p-6 border-t border-border flex items-center justify-between gap-3">
      <button
        type="button"
        onClick={onReject}
        className="flex items-center gap-2 px-4 py-2 border border-border rounded-lg hover:bg-accent transition-colors"
      >
        <X className="w-4 h-4" />
        {t("aiActions.reject")}
      </button>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onInsertAsNew}
          className="flex items-center gap-2 px-4 py-2 border border-border rounded-lg hover:bg-accent transition-colors"
          title={t("aiActions.insertAsNew")}
        >
          <Plus className="w-4 h-4" />
          {t("aiActions.insertAsNew")}
        </button>
        <button
          type="button"
          onClick={onNewSuggestions}
          className="flex items-center gap-2 px-4 py-2 border border-border rounded-lg hover:bg-accent transition-colors"
        >
          <RotateCcw className="w-4 h-4" />
          {t("aiActions.newSuggestions")}
        </button>
        <button
          type="button"
          onClick={onAccept}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition-opacity"
        >
          <Check className="w-4 h-4" />
          {t("aiActions.replace")}
        </button>
      </div>
    </div>
  );
}
