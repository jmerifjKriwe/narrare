"use client";

import { X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { TimelineAnalysisView } from "./TimelineAnalysisView";
import { TimelineConsistencyPanel } from "./TimelineConsistencyPanel";
import { TimelineEventList } from "./TimelineEventList";
import { TimelineExtractionReview } from "./TimelineExtractionReview";

type TimelineTab = "events" | "analysis" | "consistency" | "extract";

interface TimelinePanelProps {
  novelId: string;
  onClose?: () => void;
}

/** Main container for the Timeline feature. Manages tab state and data fetching. */
export function TimelinePanel({ novelId, onClose }: TimelinePanelProps) {
  const t = useTranslations("timeline");
  const [activeTab, setActiveTab] = useState<TimelineTab>("events");

  const tabs: { key: TimelineTab; label: string }[] = [
    { key: "events", label: t("eventsTab") },
    { key: "analysis", label: t("analysisTab") },
    { key: "consistency", label: t("consistencyTab") },
    { key: "extract", label: t("extractTab") },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Header with tabs */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-border bg-card">
        <h3 className="text-sm font-medium flex-1">{t("title")}</h3>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded hover:bg-[var(--color-bg-secondary)] transition-colors text-muted-foreground"
            aria-label={t("close")}
          >
            <X className="w-4 h-4" />
          </button>
        )}
        <div className="flex rounded-md border border-border overflow-hidden">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                "px-3 py-1 text-xs font-medium transition-colors",
                activeTab === tab.key
                  ? "bg-[var(--color-accent)] text-white"
                  : "bg-card text-muted-foreground hover:bg-[var(--color-bg-secondary)]",
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-auto">
        {activeTab === "events" && <TimelineEventList novelId={novelId} />}
        {activeTab === "analysis" && <TimelineAnalysisView novelId={novelId} />}
        {activeTab === "consistency" && <TimelineConsistencyPanel novelId={novelId} />}
        {activeTab === "extract" && <TimelineExtractionReview novelId={novelId} />}
      </div>
    </div>
  );
}
