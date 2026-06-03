import type { ConsistencyCheckType, ConsistencySeverity } from "@/lib/api/analysis";
import { CHECK_TYPE_LABELS } from "./consistencyIssueConfig";

interface ConsistencyIssueFiltersProps {
  filterType: ConsistencyCheckType | "all";
  filterSeverity: ConsistencySeverity | "all";
  filteredCount: number;
  visibleCount: number;
  onFilterTypeChange: (value: ConsistencyCheckType | "all") => void;
  onFilterSeverityChange: (value: ConsistencySeverity | "all") => void;
  t: (key: string, params?: Record<string, unknown>) => string;
}

export function ConsistencyIssueFilters({
  filterType,
  filterSeverity,
  filteredCount,
  visibleCount,
  onFilterTypeChange,
  onFilterSeverityChange,
  t,
}: ConsistencyIssueFiltersProps) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <select
        value={filterType}
        onChange={(e) => onFilterTypeChange(e.target.value as ConsistencyCheckType | "all")}
        className="text-xs border border-border rounded-md px-2 py-1 bg-background"
        aria-label={t("consistency.filterByType")}
      >
        <option value="all">{t("consistency.allTypes")}</option>
        {Object.entries(CHECK_TYPE_LABELS).map(([key, label]) => (
          <option key={key} value={key}>
            {label}
          </option>
        ))}
      </select>

      <select
        value={filterSeverity}
        onChange={(e) => onFilterSeverityChange(e.target.value as ConsistencySeverity | "all")}
        className="text-xs border border-border rounded-md px-2 py-1 bg-background"
        aria-label={t("consistency.filterBySeverity")}
      >
        <option value="all">{t("consistency.allSeverities")}</option>
        <option value="error">{t("consistency.severity.error")}</option>
        <option value="warning">{t("consistency.severity.warning")}</option>
        <option value="info">{t("consistency.severity.info")}</option>
      </select>

      <span className="text-xs text-muted-foreground">
        {t("consistency.issueCount", { count: filteredCount, total: visibleCount })}
      </span>
    </div>
  );
}
