"use client";

/**
 * ConsistencyResults — Results display for consistency check.
 *
 * Shows issues grouped by category with severity badges. Dismissed findings
 * (CR-AUFG-07-26) are hidden by default and can be revealed via a toggle;
 * each card carries dismiss/undismiss controls backed by the
 * useDismissedFindings hook.
 *
 * Extracted from ConsistencyCheckPanel for RULE-04 compliance.
 */

import { Check } from "lucide-react";
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";
import type { ConsistencyCheckResponse } from "@/lib/api/consistency";
import { consistencyFingerprint } from "@/lib/api/consistency";
import type { ConsistencyIssue } from "@/lib/api/worldbuilding";
import { useDismissedFindings } from "@/lib/hooks/useDismissedFindings";
import { ConsistencyCard, groupByCategory } from "./WorldbuildingAnalysisCards";

const SEVERITY_ORDER: Record<string, number> = { critical: 0, major: 1, minor: 2, info: 3 };

interface ConsistencyResultsProps {
  readonly novelId: string;
  readonly result: ConsistencyCheckResponse;
  readonly onEntityClick?: (entityId: string) => void;
}

export function ConsistencyResults({ novelId, result, onEntityClick }: ConsistencyResultsProps) {
  const t = useTranslations("studio");
  const [showDismissed, setShowDismissed] = useState(false);
  const { dismissedFingerprints, dismiss, undismiss } = useDismissedFindings(novelId);

  // Pre-compute fingerprints so filter + card props share the same key.
  const issuesWithFp = useMemo(
    () =>
      result.issues.map((issue) => ({
        issue,
        fingerprint: consistencyFingerprint(issue),
      })),
    [result.issues],
  );

  const hasDismissed = issuesWithFp.some(({ fingerprint }) =>
    dismissedFingerprints.has(fingerprint),
  );

  const visibleIssues = useMemo(
    () =>
      showDismissed
        ? issuesWithFp
        : issuesWithFp.filter(({ fingerprint }) => !dismissedFingerprints.has(fingerprint)),
    [issuesWithFp, dismissedFingerprints, showDismissed],
  );

  if (result.issues.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <div className="w-12 h-12 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center mb-4">
          <Check className="w-6 h-6 text-green-500" />
        </div>
        <p className="text-lg font-medium mb-1">{t("consistency.noIssues")}</p>
        <p className="text-sm text-muted-foreground">{t("worldbuilding.noIssuesDesc")}</p>
      </div>
    );
  }

  const grouped = groupByCategory(visibleIssues.map(({ issue }) => issue));

  return (
    <div className="space-y-6">
      {hasDismissed && (
        <button
          type="button"
          onClick={() => setShowDismissed((prev) => !prev)}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          {showDismissed ? t("kb.hideDismissed") : t("kb.showDismissed")}
        </button>
      )}
      {Object.entries(grouped).map(([category, categoryIssues]) => (
        <div key={category}>
          <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-3">
            {category.replace(/_/g, " ")}
            <span className="ml-2 text-xs">({categoryIssues.length})</span>
          </h4>
          <div className="space-y-3">
            {categoryIssues
              .sort(
                (a: ConsistencyIssue, b: ConsistencyIssue) =>
                  (SEVERITY_ORDER[a.severity] ?? 99) - (SEVERITY_ORDER[b.severity] ?? 99),
              )
              .map((issue: ConsistencyIssue) => {
                const fingerprint = consistencyFingerprint(issue);
                const isDismissed = dismissedFingerprints.has(fingerprint);
                return (
                  <ConsistencyCard
                    key={issue.finding_index}
                    issue={issue}
                    t={t}
                    onEntityClick={onEntityClick}
                    dismissed={isDismissed}
                    onDismiss={isDismissed ? undefined : dismiss}
                    onUndismiss={isDismissed ? undismiss : undefined}
                  />
                );
              })}
          </div>
        </div>
      ))}
    </div>
  );
}
