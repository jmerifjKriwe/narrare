"use client";

import { Sparkles, Trash2 } from "lucide-react";
import type { useTranslations } from "next-intl";
import type { ComponentType } from "react";
import type { KBEntityType } from "@/lib/api/kb";
import type { KBCreationSession } from "@/lib/api/kb-sessions";

type StudioTranslator = ReturnType<typeof useTranslations>;

interface HeaderProps {
  entityType: KBEntityType;
  EntityIcon: ComponentType<{ className?: string }>;
  session: KBCreationSession;
  filledFields: number;
  totalFields: number;
  resumePersistenceEnabled: boolean;
  onResumePersistenceChange: (enabled: boolean) => void;
  onAbandon: () => void;
  t: StudioTranslator;
}

export function KBAssistedCreationHeader({
  entityType,
  EntityIcon,
  session,
  filledFields,
  totalFields,
  resumePersistenceEnabled,
  onResumePersistenceChange,
  onAbandon,
  t,
}: HeaderProps) {
  return (
    <div className="border-b border-border bg-card p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-purple-600 dark:text-purple-400" />
          </div>
          <div>
            <h2 className="font-medium">{t("kb.aiAssistedCreation") || "AI-Assisted Creation"}</h2>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <EntityIcon className="w-3.5 h-3.5" />
              <span>{t(`kb.${entityType}s`) || entityType}</span>
              <span className="text-xs px-2 py-0.5 rounded bg-muted">
                {session.status === "active"
                  ? t("kb.statusActive") || "Active"
                  : session.status === "review"
                    ? t("kb.statusReview") || "Review"
                    : session.status}
              </span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={resumePersistenceEnabled}
              onChange={(event) => onResumePersistenceChange(event.target.checked)}
              className="h-4 w-4 rounded border-border"
              aria-label={t("kb.interview.resumePersistenceToggle")}
            />
            <span>{t("kb.interview.resumePersistenceToggle")}</span>
          </label>
          <button
            type="button"
            onClick={onAbandon}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground rounded-md hover:bg-muted transition-colors"
          >
            <Trash2 className="w-4 h-4" />
            {t("kb.abandon")}
          </button>
        </div>
      </div>
      <div className="flex items-center justify-between text-xs text-muted-foreground mb-1.5">
        <span>{t("kb.sessionProgress", { filled: filledFields, total: totalFields })}</span>
        <span>{totalFields > 0 ? `${Math.round((filledFields / totalFields) * 100)}%` : "0%"}</span>
      </div>
      <div className="h-1.5 bg-muted rounded-full overflow-hidden">
        <div
          className="h-full bg-purple-500 transition-all duration-300"
          style={{ width: totalFields > 0 ? `${(filledFields / totalFields) * 100}%` : "0%" }}
        />
      </div>
    </div>
  );
}
