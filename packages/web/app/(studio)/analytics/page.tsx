"use client";

/**
 * Analytics — /analytics (STATS-002, ADR-093 §5).
 *
 * Client page owning the section tab state: v1 ships a single "AI Costs" tab
 * rendering AnalyticsCostsPanel; STATS-001 adds further tabs via PanelTabs.
 * Lives in the (studio) group so the AuthGate applies — mirrors /scratchpad.
 */
import { Coins } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { AnalyticsCostsPanel } from "@/components/analytics/AnalyticsCostsPanel";
import { PanelTabs } from "@/components/ui/panel-tabs";

const COSTS_TAB_ID = "costs";

export default function AnalyticsPage() {
  const t = useTranslations("analytics.costs");
  const [activeTab, setActiveTab] = useState<string>(COSTS_TAB_ID);

  return (
    <PanelTabs
      ariaLabel={t("title")}
      value={activeTab}
      onValueChange={setActiveTab}
      tabs={[
        {
          id: COSTS_TAB_ID,
          label: t("title"),
          icon: Coins,
          content: <AnalyticsCostsPanel />,
        },
      ]}
    />
  );
}
