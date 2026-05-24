"use client";

import { ChevronDown, Info } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import type { ContextMeta } from "@/lib/api/generation";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ContextInspectorProps {
  readonly meta: ContextMeta | null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ContextInspector({ meta }: ContextInspectorProps) {
  const t = useTranslations("studio");
  const [isOpen, setIsOpen] = useState(false);

  if (!meta) return null;

  const entitySummary = [
    meta.kb_characters_count > 0 &&
      `${meta.kb_characters_count} ${t("contextInspector.characters")}`,
    meta.kb_locations_count > 0 && `${meta.kb_locations_count} ${t("contextInspector.locations")}`,
    meta.kb_factions_count > 0 && `${meta.kb_factions_count} ${t("contextInspector.factions")}`,
    meta.recent_chapter_count > 0 &&
      `${meta.recent_chapter_count} ${t("contextInspector.recentChapters")}`,
  ].filter(Boolean);

  const allNames = [...meta.character_names.slice(0, 5), ...meta.location_names.slice(0, 3)];
  const hasMore = meta.character_names.length + meta.location_names.length > 8;

  return (
    <div className="border border-border rounded-md overflow-hidden">
      {/* Header — always visible */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-accent transition-colors text-left"
        aria-label={t("contextInspector.toggle")}
      >
        <Info className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
        <span className="text-muted-foreground truncate flex-1">
          {entitySummary.length > 0 ? entitySummary.join(" · ") : t("contextInspector.noContext")}
        </span>
        <ChevronDown
          className={`w-3.5 h-3.5 text-muted-foreground transition-transform ${isOpen ? "rotate-180" : ""}`}
        />
      </button>

      {/* Expanded detail panel */}
      {isOpen && (
        <div className="border-t border-border px-3 py-2 space-y-2 bg-muted/30">
          {/* Entity chips */}
          {allNames.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {allNames.map((name) => (
                <span
                  key={name}
                  className="px-1.5 py-0.5 bg-muted rounded text-xs text-muted-foreground"
                >
                  {name}
                </span>
              ))}
              {hasMore && (
                <span className="px-1.5 py-0.5 text-xs text-muted-foreground">
                  {t("contextInspector.more")}
                </span>
              )}
            </div>
          )}

          {/* Flags */}
          <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
            {meta.has_user_preferences && <span>{t("contextInspector.preferencesActive")}</span>}
            {meta.is_first_chapter && <span>{t("contextInspector.firstChapter")}</span>}
            <span>
              {t("contextInspector.tone")}: {meta.tone}
            </span>
            {meta.total_budget_tokens > 0 && (
              <span>
                {t("contextInspector.budget")}:{" "}
                {t("contextInspector.budgetK", {
                  value: (meta.total_budget_tokens / 1000).toFixed(0),
                })}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
