"use client";

import { useTranslations } from "next-intl";
import type { BetaReaderResponse } from "@/lib/api/analysis";
import { type BetaTab, TAB_CONFIG } from "./BetaReaderPanelContent";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface BetaReaderTabBarProps {
  readonly activeTab: BetaTab;
  readonly result: BetaReaderResponse | null;
  readonly onTabChange: (tab: BetaTab) => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function countForTab(key: BetaTab, result: BetaReaderResponse | null): number {
  if (key === "strengths") return result?.strengths.length ?? 0;
  if (key === "issues") return result?.feedback.length ?? 0;
  if (key === "questions") return result?.questions.length ?? 0;
  return 0;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Tab navigation for beta reader result categories. */
export function BetaReaderTabBar({ activeTab, result, onTabChange }: BetaReaderTabBarProps) {
  const t = useTranslations("analysis");

  return (
    <div className="flex border-b border-border bg-card">
      {TAB_CONFIG.map(({ key, icon: TabIcon }) => {
        const count = countForTab(key, result);
        return (
          <button
            key={key}
            type="button"
            onClick={() => onTabChange(key)}
            className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2.5 text-sm font-medium transition-colors border-b-2 ${activeTab === key ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"}`}
          >
            <TabIcon className="w-4 h-4" />
            {t(`tabs.${key}`)}
            {key !== "overall" && (
              <span
                className={`text-xs px-1.5 py-0.5 rounded ${activeTab === key ? "bg-primary/10" : "bg-muted"}`}
              >
                {count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
