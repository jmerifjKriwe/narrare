"use client";

/**
 * ConsistencyIssueList — filterable issue card list for ConsistencyPanel.
 */

import { useCallback, useState } from "react";
import type {
  ConsistencyCheckType,
  ConsistencyIssue,
  ConsistencySeverity,
} from "@/lib/api/analysis";
import { ConsistencyIssueCard } from "./ConsistencyIssueCard";
import { ConsistencyIssueFilters } from "./ConsistencyIssueFilters";
import { issueKey } from "./consistencyIssueConfig";

interface ConsistencyIssueListProps {
  issues: ConsistencyIssue[];
  t: (key: string, params?: Record<string, unknown>) => string;
}

export function ConsistencyIssueList({ issues, t }: ConsistencyIssueListProps) {
  const [filterType, setFilterType] = useState<ConsistencyCheckType | "all">("all");
  const [filterSeverity, setFilterSeverity] = useState<ConsistencySeverity | "all">("all");
  const [dismissedKeys, setDismissedKeys] = useState<Set<string>>(new Set());
  const [intentionalKeys, setIntentionalKeys] = useState<Set<string>>(new Set());
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const visibleIssues = issues.filter((i) => !dismissedKeys.has(issueKey(i)));
  const filteredIssues = visibleIssues.filter((issue) => {
    if (filterType !== "all" && issue.check_type !== filterType) return false;
    if (filterSeverity !== "all" && issue.severity !== filterSeverity) return false;
    return true;
  });

  const handleCopy = useCallback(async (key: string, text: string) => {
    await navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  }, []);

  return (
    <div className="space-y-3">
      <ConsistencyIssueFilters
        filterType={filterType}
        filterSeverity={filterSeverity}
        filteredCount={filteredIssues.length}
        visibleCount={visibleIssues.length}
        onFilterTypeChange={setFilterType}
        onFilterSeverityChange={setFilterSeverity}
        t={t}
      />

      {filteredIssues.length > 0 ? (
        <div className="space-y-3">
          {filteredIssues.map((issue) => {
            const key = issueKey(issue);
            return (
              <ConsistencyIssueCard
                key={`issue-${issue.check_type}-${issue.severity}-${issue.description.slice(0, 30)}`}
                issue={issue}
                t={t}
                isIntentional={intentionalKeys.has(key)}
                isCopied={copiedKey === key}
                onDismiss={() => setDismissedKeys((prev) => new Set(prev).add(key))}
                onMarkIntentional={() => {
                  setIntentionalKeys((prev) => {
                    const next = new Set(prev);
                    if (next.has(key)) next.delete(key);
                    else next.add(key);
                    return next;
                  });
                }}
                onCopySuggestion={() => void handleCopy(key, issue.suggestion ?? "")}
              />
            );
          })}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <p className="text-sm text-muted-foreground">{t("consistency.noIssues")}</p>
        </div>
      )}
    </div>
  );
}
