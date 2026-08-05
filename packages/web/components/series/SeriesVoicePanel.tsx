"use client";

/**
 * SeriesVoicePanel — the functional Voice tab (Spec 3, Tasks 5–6).
 *
 * Orchestrates the series-voice lifecycle for one series:
 *
 * - Status badge: empty (no profile) / auto-profiled (a profile exists) /
 *   override-active (a manual override was just applied — optimistic local
 *   state; the backend stores a single ``author_voice`` JSONB with no
 *   provenance flag, so auto vs. manual cannot be distinguished after reload).
 * - "Profile from band…" dropdown (select a member novel) + trigger button →
 *   POST profile (one AuthorVoiceAgent LLM call, rate-limited server-side).
 * - Profile display (descriptive group only — ADR-074 binding).
 * - Override editor (JSON textarea) + clear button.
 *
 * RULE-04: the profile view and override editor live in their own modules.
 * All copy via ``useTranslations("studio")`` under ``series.voice.*``.
 */
import { Loader2, Wand2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { SeriesVoiceOverrideEditor } from "@/components/series/SeriesVoiceOverrideEditor";
import { SeriesVoiceProfileView } from "@/components/series/SeriesVoiceProfileView";
import { useSeriesNovels } from "@/lib/hooks/useSeriesNovels";
import { useProfileSeriesVoice, useSeriesVoice } from "@/lib/hooks/useSeriesVoice";

interface SeriesVoicePanelProps {
  readonly seriesId: string;
}

type Status = "empty" | "autoProfiled" | "overrideActive";

export function SeriesVoicePanel({ seriesId }: SeriesVoicePanelProps) {
  const t = useTranslations("studio");
  const { data, isLoading } = useSeriesVoice(seriesId);
  const { data: novels } = useSeriesNovels(seriesId);
  const profileVoice = useProfileSeriesVoice(seriesId);

  const [selectedNovelId, setSelectedNovelId] = useState("");
  // Local optimistic flag: set when a manual override is applied, cleared on
  // profile-regenerate / clear. The backend has no provenance column.
  const [overrideActive, setOverrideActive] = useState(false);

  if (isLoading) {
    return (
      <div
        data-testid="series-voice-loading"
        className="flex items-center gap-2 py-4 text-sm text-muted-foreground"
      >
        <Loader2 className="h-4 w-4 animate-spin" />
        {t("series.voice.loading")}
      </div>
    );
  }

  const voice = data?.author_voice ?? null;
  const status: Status =
    voice === null ? "empty" : overrideActive ? "overrideActive" : "autoProfiled";

  function handleProfile() {
    if (!selectedNovelId) return;
    // A fresh auto-profile supersedes any manual override intent.
    setOverrideActive(false);
    profileVoice.mutate(selectedNovelId);
  }

  return (
    <section data-testid="series-voice-tab" className="max-w-3xl space-y-4">
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-medium">{t("series.voice.title")}</h2>
        <span
          data-testid="series-voice-status"
          className="rounded bg-muted px-2 py-0.5 text-[10px] text-muted-foreground"
        >
          {t(`series.voice.status.${status}`)}
        </span>
      </div>

      {/* Profile-from-band dropdown */}
      <div className="space-y-2 rounded-md border border-border bg-card p-4">
        <label
          className="text-xs font-medium text-foreground"
          htmlFor="series-voice-profile-select"
        >
          {t("series.voice.profileFrom")}
        </label>
        <div className="flex items-center gap-2">
          <select
            id="series-voice-profile-select"
            data-testid="series-voice-profile-select"
            value={selectedNovelId}
            onChange={(e) => setSelectedNovelId(e.target.value)}
            className="flex-1 rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">{t("series.voice.profileFromPlaceholder")}</option>
            {(novels ?? []).map((n) => (
              <option key={n.id} value={n.id}>
                {n.title}
              </option>
            ))}
          </select>
          <button
            type="button"
            data-testid="series-voice-profile-trigger"
            onClick={handleProfile}
            disabled={!selectedNovelId || profileVoice.isPending}
            className="flex items-center gap-1 rounded bg-primary px-3 py-1 text-xs text-primary-foreground disabled:opacity-50"
          >
            {profileVoice.isPending ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Wand2 className="h-3 w-3" />
            )}
            {t("series.voice.profile")}
          </button>
        </div>
      </div>

      {voice ? (
        <>
          <SeriesVoiceProfileView profile={voice} />
          <SeriesVoiceOverrideEditor
            seriesId={seriesId}
            initialVoice={voice}
            onOverrideApplied={() => setOverrideActive(true)}
          />
        </>
      ) : null}
    </section>
  );
}
