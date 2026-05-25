"use client";

/**
 * Footer component for KB Assisted Creation Panel.
 *
 * Contains the entry name input and action buttons (interview, enhance, cancel, save).
 * Extracted to keep KBAssistedCreationPanel under file size limits.
 */

import { Sparkles, Wand2 } from "lucide-react";
import { useTranslations } from "next-intl";
import type { KBCreationSession } from "@/lib/api/kb-sessions";
import type { AssistedView } from "./KBAssistedCreationPanel";

interface KBAssistedCreationFooterProps {
  session: KBCreationSession | null | undefined;
  entryName: string;
  setEntryName: (name: string) => void;
  view: AssistedView;
  setView: (view: AssistedView) => void;
  filledFields: number;
  completePending: boolean;
  onCancel: () => void;
  onCompleteAndSave: () => void;
}

export function KBAssistedCreationFooter({
  session,
  entryName,
  setEntryName,
  setView,
  filledFields,
  completePending,
  onCancel,
  onCompleteAndSave,
}: KBAssistedCreationFooterProps) {
  const t = useTranslations("studio");

  return (
    <div className="border-t border-border bg-card">
      {/* Entry name input */}
      {session?.status !== "complete" && (
        <div className="p-4 border-b border-border">
          <label htmlFor="entry-name" className="block text-sm font-medium mb-1 text-foreground">
            {t("kb.entry_name") || "Entry Name"}
          </label>
          <input
            id="entry-name"
            type="text"
            value={entryName}
            onChange={(e) => setEntryName(e.target.value)}
            placeholder={t("kb.entry_name_placeholder") || "Enter a name for your entry"}
            className="w-full px-3 py-2 rounded-md border border-input bg-background text-sm
                       focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
      )}

      {/* Action buttons */}
      <div className="p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setView("interview")}
              className="flex items-center gap-2 px-4 py-2 border border-border rounded-md hover:bg-muted transition-colors text-sm"
            >
              <Sparkles className="w-4 h-4" />
              {t("kb.startInterview")}
            </button>
            <button
              type="button"
              onClick={() => setView("enhance")}
              disabled={filledFields === 0}
              className="flex items-center gap-2 px-4 py-2 border border-purple-300 dark:border-purple-700 text-purple-600 dark:text-purple-400 rounded-md hover:bg-purple-50 dark:hover:bg-purple-950/20 transition-colors text-sm disabled:opacity-50"
            >
              <Wand2 className="w-4 h-4" />
              {t("kb.enhanceAll")}
            </button>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground"
            >
              {t("kb.cancel")}
            </button>
            <button
              type="button"
              onClick={onCompleteAndSave}
              disabled={filledFields === 0 || !entryName.trim() || completePending}
              className="flex items-center gap-2 px-5 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity disabled:opacity-50 text-sm font-medium"
            >
              {completePending ? t("kb.saving") || "Saving..." : t("kb.completeAndSave")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
