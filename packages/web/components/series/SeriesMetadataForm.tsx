"use client";

/**
 * SeriesMetadataForm — the editable metadata fields for a Series
 * (Spec 1, Slice 4, Task 4.7).
 *
 * Extracted from SeriesSettings (RULE-04: one responsibility per file). Owns
 * the local form state (synced from the `series` prop), the diff-based PATCH
 * payload building, and the `useUpdateSeries` mutation. The status field
 * (transition-constrained) and the Voice placeholder (Spec 3) are delegated to
 * :component:`SeriesStatusSelect` / :component:`SeriesVoicePlaceholder`.
 *
 * Pattern mirrors NovelDetailsTab: local state synced from props, a `dirty`
 * flag gating an explicit Save button. All copy via
 * `useTranslations("studio")` under `series.settings.*` (keys added by 4.9).
 */
import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { useUpdateSeries } from "@/lib/hooks/useSeries";
import type { Series, SeriesStatus, SeriesUpdate } from "@/types";
import { SeriesField as Field } from "./SeriesField";
import { SeriesStatusSelect } from "./SeriesStatusSelect";
import { SeriesVoicePlaceholder } from "./SeriesVoicePlaceholder";

interface SeriesMetadataFormProps {
  readonly series: Series;
}

export function SeriesMetadataForm({ series }: SeriesMetadataFormProps) {
  const t = useTranslations("studio");
  const update = useUpdateSeries(series.id);

  const [title, setTitle] = useState(series.title);
  const [subtitle, setSubtitle] = useState(series.subtitle ?? "");
  const [description, setDescription] = useState(series.description ?? "");
  const [genre, setGenre] = useState(series.genre ?? "");
  const [writingLanguage, setWritingLanguage] = useState(series.writing_language ?? "en");
  const [status, setStatus] = useState<SeriesStatus>(series.status);
  const [plannedCount, setPlannedCount] = useState(series.planned_novel_count?.toString() ?? "");
  const [dirty, setDirty] = useState(false);

  // Re-sync when the underlying series changes (e.g. after a refetch) — but
  // ONLY while the form is clean. Guarding on `dirty` prevents a React Query
  // background refetch (new `series` object identity) from clobbering the
  // user's unsaved edits (I-F2 data-loss fix). After Save, `dirty` flips back
  // to false and the fresh server data resyncs in.
  useEffect(() => {
    if (dirty) return;
    setTitle(series.title);
    setSubtitle(series.subtitle ?? "");
    setDescription(series.description ?? "");
    setGenre(series.genre ?? "");
    setWritingLanguage(series.writing_language ?? "en");
    setStatus(series.status);
    setPlannedCount(series.planned_novel_count?.toString() ?? "");
  }, [series, dirty]);

  function markDirty<T>(setter: (v: T) => void) {
    return (v: T) => {
      setter(v);
      setDirty(true);
    };
  }

  function buildPayload(): SeriesUpdate {
    const payload: SeriesUpdate = {};
    if (title !== series.title) payload.title = title;
    if ((subtitle.trim() || null) !== (series.subtitle ?? null)) {
      payload.subtitle = subtitle.trim() || null;
    }
    if ((description.trim() || null) !== (series.description ?? null)) {
      payload.description = description.trim() || null;
    }
    if ((genre.trim() || null) !== (series.genre ?? null)) {
      payload.genre = genre.trim() || null;
    }
    if ((writingLanguage.trim() || null) !== (series.writing_language ?? null)) {
      payload.writing_language = writingLanguage.trim() || null;
    }
    if (status !== series.status) payload.status = status;
    const parsed = plannedCount.trim() === "" ? null : Number(plannedCount);
    if (parsed !== series.planned_novel_count) payload.planned_novel_count = parsed;
    return payload;
  }

  function handleSave(): void {
    const payload = buildPayload();
    if (Object.keys(payload).length > 0) {
      update.mutate(payload, { onSuccess: () => setDirty(false) });
    }
  }

  const inputClass =
    "w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring";

  return (
    <>
      <div className="space-y-4 rounded-lg border border-border bg-card p-6">
        <Field label={t("series.settings.fields.title")}>
          <input
            data-testid="series-settings-title"
            type="text"
            value={title}
            onChange={(e) => markDirty(setTitle)(e.target.value)}
            aria-label={t("series.settings.fields.title")}
            className={inputClass}
          />
        </Field>
        <Field label={t("series.settings.fields.subtitle")}>
          <input
            data-testid="series-settings-subtitle"
            type="text"
            value={subtitle}
            onChange={(e) => markDirty(setSubtitle)(e.target.value)}
            aria-label={t("series.settings.fields.subtitle")}
            className={inputClass}
          />
        </Field>
        <Field label={t("series.settings.fields.description")}>
          <textarea
            data-testid="series-settings-description"
            value={description}
            onChange={(e) => markDirty(setDescription)(e.target.value)}
            aria-label={t("series.settings.fields.description")}
            rows={3}
            className={inputClass}
          />
        </Field>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label={t("series.settings.fields.genre")}>
            <input
              data-testid="series-settings-genre"
              type="text"
              value={genre}
              onChange={(e) => markDirty(setGenre)(e.target.value)}
              aria-label={t("series.settings.fields.genre")}
              className={inputClass}
            />
          </Field>
          <Field label={t("series.settings.fields.writingLanguage")}>
            <input
              data-testid="series-settings-writing-language"
              type="text"
              value={writingLanguage}
              onChange={(e) => markDirty(setWritingLanguage)(e.target.value)}
              aria-label={t("series.settings.fields.writingLanguage")}
              className={inputClass}
            />
          </Field>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label={t("series.settings.fields.status")}>
            <SeriesStatusSelect
              currentStatus={series.status}
              value={status}
              onChange={(next) => markDirty(setStatus)(next)}
            />
          </Field>
          <Field label={t("series.settings.fields.plannedNovelCount")}>
            <input
              data-testid="series-settings-planned-count"
              type="number"
              min={0}
              value={plannedCount}
              onChange={(e) => markDirty(setPlannedCount)(e.target.value)}
              aria-label={t("series.settings.fields.plannedNovelCount")}
              className={inputClass}
            />
          </Field>
        </div>
      </div>

      <SeriesVoicePlaceholder />

      {dirty ? (
        <div className="flex justify-end">
          <button
            type="button"
            data-testid="series-settings-save"
            onClick={handleSave}
            disabled={update.isPending}
            className="flex items-center gap-2 rounded-md bg-primary px-6 py-2.5 text-sm font-medium text-primary-foreground shadow-sm transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {update.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {t("series.settings.save")}
          </button>
        </div>
      ) : null}
    </>
  );
}
