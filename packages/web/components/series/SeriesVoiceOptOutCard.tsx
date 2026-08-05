"use client";

/**
 * SeriesVoiceOptOutCard — per-novel "use series voice as base" toggle
 * (Spec 3, Task 6).
 *
 * Persisted as ``ProjectSettings.use_series_voice`` (ADR-078 Delta-model
 * opt-out). When off, the novel falls back to its own ``author_voice`` only;
 * the series voice is skipped at generation-assembly time.
 *
 * Renders nothing for a standalone novel (``seriesId === null``) — the toggle
 * is meaningless outside a series. The card is self-contained: it fetches the
 * project settings and PATCHes the single flag, so it can drop into any novel
 * settings surface without a parent data lift.
 *
 * All copy via ``useTranslations("studio")`` under ``novel.settings.useSeriesVoice.*``.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { settingsApi } from "@/lib/api/settings";

interface SeriesVoiceOptOutCardProps {
  readonly novelId: string;
  /** ``null`` for a standalone novel → the card renders nothing. */
  readonly seriesId: string | null;
}

const PROJECT_QUERY_KEY = (novelId: string) => ["settings", "novel", novelId] as const;

export function SeriesVoiceOptOutCard({ novelId, seriesId }: SeriesVoiceOptOutCardProps) {
  const t = useTranslations("studio");
  const queryClient = useQueryClient();

  const inSeries = seriesId !== null;

  const { data } = useQuery({
    queryKey: PROJECT_QUERY_KEY(novelId),
    queryFn: () => settingsApi.getProject(novelId),
    // Don't fetch for a standalone novel — the toggle is meaningless outside
    // a series and the card renders nothing anyway.
    enabled: inSeries,
  });

  const update = useMutation({
    mutationFn: (useSeriesVoice: boolean) =>
      settingsApi.updateProject(novelId, { use_series_voice: useSeriesVoice }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PROJECT_QUERY_KEY(novelId) });
    },
  });

  // Standalone novel → the Delta model does not apply; hide the toggle.
  // (After all hooks — Rules of Hooks.)
  if (!inSeries) return null;

  const checked = data?.use_series_voice ?? true;

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    update.mutate(e.target.checked);
  }

  return (
    <div
      data-testid="series-voice-opt-out"
      className="space-y-1 rounded-lg border border-border bg-card p-4"
    >
      <label className="flex items-start gap-3" htmlFor="series-voice-opt-out-toggle">
        <input
          id="series-voice-opt-out-toggle"
          data-testid="series-voice-opt-out-toggle"
          type="checkbox"
          checked={checked}
          onChange={handleChange}
          disabled={update.isPending}
          className="mt-0.5 h-4 w-4 rounded border-border"
        />
        <span className="space-y-1">
          <span className="block text-sm font-medium text-foreground">
            {t("novel.settings.useSeriesVoice.label")}
          </span>
          <span className="block text-xs text-muted-foreground">
            {t("novel.settings.useSeriesVoice.description")}
          </span>
        </span>
      </label>
    </div>
  );
}
