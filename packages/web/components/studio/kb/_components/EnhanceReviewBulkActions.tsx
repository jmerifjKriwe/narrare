"use client";

/**
 * Bulk actions bar for enhancement review.
 *
 * Shows the count of enhancements found and select all/none controls.
 */

interface EnhanceReviewBulkActionsProps {
  count: number;
  onSelectAll: () => void;
  onSelectNone: () => void;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}

export function EnhanceReviewBulkActions({
  count,
  onSelectAll,
  onSelectNone,
  t,
}: EnhanceReviewBulkActionsProps) {
  return (
    <div className="flex items-center justify-between p-3 bg-muted/30 rounded-lg">
      <div className="flex items-center gap-3">
        <span className="text-sm text-muted-foreground">
          {t("kb.enhancementsFound", { count })}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onSelectAll}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          {t("kb.selectAll")}
        </button>
        <span className="text-muted-foreground">|</span>
        <button
          type="button"
          onClick={onSelectNone}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          {t("kb.selectNone")}
        </button>
      </div>
    </div>
  );
}
