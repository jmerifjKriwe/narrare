"use client";

/**
 * SeriesStatusSelect — status field constrained to the backend's adjacency
 * matrix (Spec 1, Slice 4, Task 4.7).
 *
 * Extracted from SeriesMetadataForm (RULE-04). Only reachable status
 * transitions are offered (draft→active→completed; mirrors
 * apps/api/narrare/series/service.py `_TRANSITIONS`). The allowed option set
 * is derived from the Series' *actual* status (`currentStatus`), while the
 * selected value is the local form state (`value`). Copy via
 * `useTranslations("studio")` under `series.settings.*`.
 */
import { useTranslations } from "next-intl";
import type { SeriesStatus } from "@/types";

const TRANSITIONS: Record<SeriesStatus, SeriesStatus[]> = {
  draft: ["draft", "active"],
  active: ["active", "completed", "draft"],
  completed: ["completed", "draft"],
};

interface SeriesStatusSelectProps {
  /** The Series' actual status — defines the allowed transition targets. */
  readonly currentStatus: SeriesStatus;
  /** The currently selected (local form) status. */
  readonly value: SeriesStatus;
  readonly onChange: (status: SeriesStatus) => void;
}

export function SeriesStatusSelect({ currentStatus, value, onChange }: SeriesStatusSelectProps) {
  const t = useTranslations("studio");
  const statusOptions = TRANSITIONS[currentStatus];

  return (
    <select
      data-testid="series-settings-status"
      value={value}
      onChange={(e) => onChange(e.target.value as SeriesStatus)}
      aria-label={t("series.settings.fields.status")}
      className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
    >
      {statusOptions.map((option) => (
        <option key={option} value={option}>
          {t(`series.settings.status.${option}`)}
        </option>
      ))}
    </select>
  );
}
