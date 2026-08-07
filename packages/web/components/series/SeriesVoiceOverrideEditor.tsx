"use client";

/**
 * SeriesVoiceOverrideEditor — manual voice-profile override editor
 * (Spec 3, Tasks 5–6).
 *
 * A JSON textarea that PATCHes a full ``author_voice`` profile dict (validated
 * server-side as ``AuthorVoiceProfile``; a malformed override → 422). The
 * textarea is prefilled with the current profile so the user can tweak the full
 * shape. Controls:
 *
 * - Save Override → PATCH (``useUpdateSeriesVoiceOverride``); validates JSON
 *   locally first and surfaces an inline error when parsing fails.
 * - Clear Override → DELETE (``useClearSeriesVoiceOverride``).
 *
 * Extracted from ``SeriesVoicePanel`` (RULE-04: modularize, don't compress).
 * All copy via ``useTranslations("studio")`` under ``series.voice.*``.
 */
import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import {
  useClearSeriesVoiceOverride,
  useUpdateSeriesVoiceOverride,
} from "@/lib/hooks/useSeriesVoice";
import type { SeriesVoiceProfile } from "@/types";

interface SeriesVoiceOverrideEditorProps {
  readonly seriesId: string;
  readonly initialVoice: SeriesVoiceProfile | null;
  /**
   * Fired after a manual override is successfully PATCHed. The panel uses this
   * to flip its status badge to "override active" — the backend stores a single
   * ``author_voice`` column with no provenance flag, so the auto-vs-manual
   * distinction is a local optimistic state owned by the panel.
   */
  readonly onOverrideApplied?: () => void;
}

export function SeriesVoiceOverrideEditor({
  seriesId,
  initialVoice,
  onOverrideApplied,
}: SeriesVoiceOverrideEditorProps) {
  const t = useTranslations("studio");
  const updateOverride = useUpdateSeriesVoiceOverride(seriesId);
  const clearOverride = useClearSeriesVoiceOverride(seriesId);

  const [text, setText] = useState(() =>
    initialVoice ? JSON.stringify(initialVoice, null, 2) : "",
  );
  const [dirty, setDirty] = useState(false);
  const [parseError, setParseError] = useState(false);

  // Re-sync from the server while clean (mirrors BandOverrideEditor /
  // SeriesMetadataForm) so a background refetch updates the prefilled JSON.
  useEffect(() => {
    if (dirty) return;
    setText(initialVoice ? JSON.stringify(initialVoice, null, 2) : "");
  }, [initialVoice, dirty]);

  function handleSave() {
    const trimmed = text.trim();
    if (trimmed === "") return;
    let parsed: unknown;
    try {
      parsed = JSON.parse(trimmed);
    } catch {
      setParseError(true);
      return;
    }
    setParseError(false);
    if (parsed === null || typeof parsed !== "object") {
      setParseError(true);
      return;
    }
    updateOverride.mutate(
      { author_voice: parsed as Record<string, unknown> },
      {
        onSuccess: () => {
          setDirty(false);
          onOverrideApplied?.();
        },
      },
    );
  }

  const saveDisabled = updateOverride.isPending || text.trim() === "";

  return (
    <div className="space-y-2">
      <label
        className="text-xs font-medium text-foreground"
        htmlFor="series-voice-override-textarea"
      >
        {t("series.voice.override")}
      </label>
      <textarea
        id="series-voice-override-textarea"
        data-testid="series-voice-override-input"
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          setDirty(true);
          setParseError(false);
        }}
        rows={8}
        spellCheck={false}
        placeholder={t("series.voice.overridePlaceholder")}
        className="w-full rounded-md border border-border bg-background px-2 py-1.5 font-mono text-xs focus:outline-none focus:ring-2 focus:ring-ring"
        aria-invalid={parseError}
      />
      {parseError ? (
        <p data-testid="series-voice-override-error" className="text-xs text-destructive">
          {t("series.voice.overrideInvalid")}
        </p>
      ) : null}
      <div className="flex items-center gap-2">
        <button
          type="button"
          data-testid="series-voice-save-override"
          onClick={handleSave}
          disabled={saveDisabled}
          className="flex items-center gap-1 rounded bg-primary px-3 py-1 text-xs text-primary-foreground disabled:opacity-50"
        >
          {updateOverride.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
          {t("series.voice.saveOverride")}
        </button>
        <button
          type="button"
          data-testid="series-voice-clear-override"
          onClick={() => clearOverride.mutate()}
          disabled={clearOverride.isPending}
          className="text-xs text-destructive hover:underline disabled:opacity-50"
        >
          {t("series.voice.clearOverride")}
        </button>
      </div>
    </div>
  );
}
