"use client";

/**
 * KB Category Sidebar — Column 1 of the 3-column KB browser.
 *
 * Shows entity type tabs with count badges and an "All" option.
 */

import { BookOpen, Network, ShieldCheck, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import type { KBEntityType } from "@/lib/api/kb";
import { useKBEntries } from "@/lib/hooks/useKB";
import { useWikiIndex } from "@/lib/hooks/useWiki";
import { ENTITY_TYPES, TYPE_ICONS, TYPE_LABEL_KEYS } from "./constants";

interface KBCategorySidebarProps {
  novelId: string;
  activeType: KBEntityType | null;
  onTypeChange: (type: KBEntityType | null) => void;
  onAnalyze?: () => void;
  onConsistencyCheck?: () => void;
  onShowGraph?: () => void;
  onShowWiki?: () => void;
  showGraph?: boolean;
  showWiki?: boolean;
}

export function KBCategorySidebar({
  novelId,
  activeType,
  onTypeChange,
  onAnalyze,
  onConsistencyCheck,
  onShowGraph,
  onShowWiki,
  showGraph,
  showWiki,
}: KBCategorySidebarProps) {
  const t = useTranslations("studio");

  // Fetch counts for each entity type
  const { data: allData } = useKBEntries(novelId, { page_size: 1 });
  const totalCount = allData?.total ?? 0;

  // Fetch wiki index for pending count badge
  const { data: wikiIndex } = useWikiIndex(novelId);
  const wikiPendingCount = wikiIndex?.pending_count ?? 0;

  return (
    <div className="w-56 border-r border-border bg-card flex flex-col">
      <div className="p-4 border-b border-border">
        <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
          {t("kb.title")}
        </h2>
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        <div className="space-y-0.5">
          {/* "All" tab */}
          <button
            type="button"
            onClick={() => onTypeChange(null)}
            className={`w-full flex items-center justify-between gap-3 px-3 py-2 rounded-md transition-all text-sm ${
              activeType === null && !showGraph
                ? "bg-primary text-primary-foreground shadow-sm"
                : "hover:bg-accent text-foreground"
            }`}
          >
            <span>{t("kb.allTypes")}</span>
            <span
              className={`text-xs px-1.5 py-0.5 rounded ${
                activeType === null && !showGraph
                  ? "bg-primary-foreground/20"
                  : "bg-muted text-muted-foreground"
              }`}
            >
              {totalCount}
            </span>
          </button>

          {/* "Graph" tab */}
          {onShowGraph && (
            <button
              type="button"
              onClick={onShowGraph}
              className={`w-full flex items-center justify-between gap-3 px-3 py-2 rounded-md transition-all text-sm ${
                showGraph
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "hover:bg-accent text-foreground"
              }`}
            >
              <span className="flex items-center gap-3">
                <Network className="w-4 h-4" />
                <span>{t("graph.title")}</span>
              </span>
            </button>
          )}

          {/* "Wiki" tab */}
          {onShowWiki && (
            <button
              type="button"
              onClick={onShowWiki}
              className={`w-full flex items-center justify-between gap-3 px-3 py-2 rounded-md transition-all text-sm ${
                showWiki
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "hover:bg-accent text-foreground"
              }`}
            >
              <span className="flex items-center gap-3">
                <BookOpen className="w-4 h-4" />
                <span>{t("kb.wiki.tabLabel")}</span>
              </span>
              {wikiPendingCount > 0 && (
                <span
                  className={`text-xs px-1.5 py-0.5 rounded ${
                    showWiki
                      ? "bg-primary-foreground/20"
                      : "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400"
                  }`}
                >
                  {wikiPendingCount}
                </span>
              )}
            </button>
          )}

          {/* Per-type tabs */}
          {ENTITY_TYPES.map((type) => (
            <TypeButton
              key={type}
              novelId={novelId}
              type={type}
              isActive={activeType === type}
              onClick={() => onTypeChange(type)}
            />
          ))}
        </div>
      </div>
      {/* Analyze Worldbuilding button */}
      {(onAnalyze || onConsistencyCheck) && (
        <div className="p-2 border-t border-border space-y-1.5">
          {onAnalyze && (
            <button
              type="button"
              onClick={onAnalyze}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-md bg-purple-50 dark:bg-purple-900/20 text-purple-700 dark:text-purple-400 hover:bg-purple-100 dark:hover:bg-purple-900/30 transition-colors text-sm font-medium"
            >
              <Sparkles className="w-4 h-4" />
              {t("worldbuilding.analyzeButton") || "Analyze Worldbuilding"}
            </button>
          )}
          {onConsistencyCheck && (
            <button
              type="button"
              onClick={onConsistencyCheck}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-md bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 hover:bg-amber-100 dark:hover:bg-amber-900/30 transition-colors text-sm font-medium"
            >
              <ShieldCheck className="w-4 h-4" />
              {t("consistency.checkButton") || "Check Consistency"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// --- Per-type button with live count ---

interface TypeButtonProps {
  novelId: string;
  type: KBEntityType;
  isActive: boolean;
  onClick: () => void;
}

function TypeButton({ novelId, type, isActive, onClick }: TypeButtonProps) {
  const t = useTranslations("studio");
  const Icon = TYPE_ICONS[type];

  const { data } = useKBEntries(novelId, { entity_type: type, page_size: 1 });
  const count = data?.total ?? 0;

  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full flex items-center justify-between gap-3 px-3 py-2 rounded-md transition-all text-sm ${
        isActive
          ? "bg-primary text-primary-foreground shadow-sm"
          : "hover:bg-accent text-foreground"
      }`}
    >
      <span className="flex items-center gap-3">
        <Icon className="w-4 h-4" />
        <span>{t(TYPE_LABEL_KEYS[type])}</span>
      </span>
      <span
        className={`text-xs px-1.5 py-0.5 rounded ${
          isActive ? "bg-primary-foreground/20" : "bg-muted text-muted-foreground"
        }`}
      >
        {count}
      </span>
    </button>
  );
}
