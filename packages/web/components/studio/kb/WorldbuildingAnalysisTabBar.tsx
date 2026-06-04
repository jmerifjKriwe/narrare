"use client";

import { Link2, Search, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import type { WorldbuildingAnalysisResponse } from "@/lib/api/worldbuilding";
import type { AnalysisTab } from "./useWorldbuildingAnalysis";

const TAB_CONFIG: { key: AnalysisTab; icon: typeof Sparkles }[] = [
  { key: "gaps", icon: Search },
  { key: "connections", icon: Link2 },
  { key: "consistency", icon: Sparkles },
];

interface WorldbuildingAnalysisTabBarProps {
  activeTab: AnalysisTab;
  analysis: WorldbuildingAnalysisResponse | null;
  onActiveTabChange: (tab: AnalysisTab) => void;
}

export function WorldbuildingAnalysisTabBar({
  activeTab,
  analysis,
  onActiveTabChange,
}: WorldbuildingAnalysisTabBarProps) {
  const t = useTranslations("studio");

  return (
    <div className="flex border-b border-border bg-card">
      {TAB_CONFIG.map(({ key, icon: TabIcon }) => {
        const count =
          key === "gaps"
            ? (analysis?.gap_findings.length ?? 0)
            : key === "connections"
              ? (analysis?.connection_suggestions.length ?? 0)
              : (analysis?.consistency_issues.length ?? 0);
        return (
          <button
            key={key}
            type="button"
            onClick={() => onActiveTabChange(key)}
            className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2.5 text-sm font-medium transition-colors border-b-2 ${activeTab === key ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"}`}
          >
            <TabIcon className="w-4 h-4" />
            {t(`worldbuilding.${key}`) || key.charAt(0).toUpperCase() + key.slice(1)}
            <span
              className={`text-xs px-1.5 py-0.5 rounded ${activeTab === key ? "bg-primary/10" : "bg-muted"}`}
            >
              {count}
            </span>
          </button>
        );
      })}
    </div>
  );
}
