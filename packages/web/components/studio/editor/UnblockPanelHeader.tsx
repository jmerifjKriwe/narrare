"use client";

/**
 * UnblockPanelHeader — title bar of the Unblock panel (WRITE-009).
 *
 * Renders the panel title (with a Lightbulb glyph) and a close button. Extracted
 * from {@link UnblockPanel} for single responsibility and to keep the panel under
 * the file-size limit (RULE-04 / RULE-06).
 *
 * @module UnblockPanelHeader
 */

import { Lightbulb, X } from "lucide-react";
import type { useTranslations } from "next-intl";

type StudioTranslator = ReturnType<typeof useTranslations>;

interface UnblockPanelHeaderProps {
  /** Called when the close button is clicked. */
  readonly onClose: () => void;
  /** Studio-scoped translator (useTranslations("studio")). */
  readonly t: StudioTranslator;
}

export function UnblockPanelHeader({ onClose, t }: UnblockPanelHeaderProps) {
  return (
    <div className="flex items-center justify-between border-b border-border bg-card p-4">
      <div className="flex items-center gap-2">
        <Lightbulb className="h-5 w-5 text-primary" />
        <h3 id="unblock-panel-title" className="font-medium">
          {t("unblock.title")}
        </h3>
      </div>
      <button
        type="button"
        onClick={onClose}
        aria-label={t("unblock.button")}
        className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
