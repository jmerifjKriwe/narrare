"use client";

/**
 * Analytics — /analytics (STATS-002, ADR-093 §5; STATS-001, ADR-095).
 *
 * Client page owning the section tab state: "AI Costs" (AnalyticsCostsPanel)
 * and "Writing" (WritingStatsPanel) via PanelTabs. Lives in the (studio)
 * group so the AuthGate applies — mirrors /scratchpad.
 */
import { Coins, PenLine } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { AnalyticsCostsPanel } from "@/components/analytics/AnalyticsCostsPanel";
import { WritingStatsPanel } from "@/components/analytics/WritingStatsPanel";
import { PanelTabs } from "@/components/ui/panel-tabs";

const COSTS_TAB_ID = "costs";
const WRITING_TAB_ID = "writing";

export default function AnalyticsPage() {
  const tSection = useTranslations("analytics");
  const tCosts = useTranslations("analytics.costs");
  const tWriting = useTranslations("analytics.writing");
  const [activeTab, setActiveTab] = useState<string>(COSTS_TAB_ID);

  return (
    <PanelTabs
      ariaLabel={tSection("sectionLabel")}
      value={activeTab}
      onValueChange={setActiveTab}
      tabs={[
        {
          id: COSTS_TAB_ID,
          label: tCosts("title"),
          icon: Coins,
          content: <AnalyticsCostsPanel />,
        },
        {
          id: WRITING_TAB_ID,
          label: tWriting("title"),
          icon: PenLine,
          content: <WritingStatsPanel />,
        },
      ]}
    />
  );
}
