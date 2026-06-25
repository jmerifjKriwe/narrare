"use client";

/**
 * UnblockInputForm — the "describe what you're stuck on" form (WRITE-009).
 *
 * Shown while the panel is idle (and re-shown after the user dismisses results).
 * The textarea ref is owned by the parent ({@link UnblockPanel}) so focus can be
 * restored programmatically on open / dismiss. Extracted from {@link UnblockPanel}
 * for single responsibility and to keep the panel under the file-size limit
 * (RULE-04 / RULE-06).
 *
 * @module UnblockInputForm
 */

import { Sparkles } from "lucide-react";
import type { useTranslations } from "next-intl";
import type { RefObject } from "react";

type StudioTranslator = ReturnType<typeof useTranslations>;

interface UnblockInputFormProps {
  /** Textarea ref — owned by the parent for focus management. */
  readonly textareaRef: RefObject<HTMLTextAreaElement | null>;
  /** Current "stuck" description text. */
  readonly stuckText: string;
  /** Called when the user edits the description. */
  readonly onStuckTextChange: (value: string) => void;
  /** Called when the user requests suggestions. */
  readonly onGetSuggestions: () => void;
  /** Studio-scoped translator (useTranslations("studio")). */
  readonly t: StudioTranslator;
}

export function UnblockInputForm({
  textareaRef,
  stuckText,
  onStuckTextChange,
  onGetSuggestions,
  t,
}: UnblockInputFormProps) {
  return (
    <div className="space-y-3">
      <label htmlFor="unblock-stuck" className="block text-sm">
        {t("unblock.stuckLabel")}
      </label>
      <textarea
        ref={textareaRef}
        id="unblock-stuck"
        value={stuckText}
        onChange={(e) => onStuckTextChange(e.target.value)}
        rows={3}
        className="w-full rounded-lg border border-border bg-input-background px-3 py-2 text-sm"
      />
      <button
        type="button"
        onClick={onGetSuggestions}
        className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground transition-colors hover:bg-primary/90"
      >
        <Sparkles className="h-4 w-4" />
        {t("unblock.getSuggestions")}
      </button>
    </div>
  );
}
