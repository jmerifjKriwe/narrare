"use client";

import { useTranslations } from "next-intl";

/**
 * ImportSuggestExtractBanner — neutral sibling card offering a bulk KB
 * extraction of the freshly imported chapters (F2 T8, ADR-092 spec §8.1,
 * D9a). Consumes the wizard's `narrare:importSuggestExtract:{novel_id}`
 * flag: the parent (importing/ImportLaunchSection) reads/clears the flag and
 * owns the panel open state — this component is presentational, mirroring
 * `ImportFailedBanner` (copy single-sourced from the "importing" namespace).
 * A suggestion, not an error: no `role="alert"`, one dismiss.
 */
interface ImportSuggestExtractBannerProps {
  /** Chapters suggested for extraction (from the stored flag payload). */
  readonly chapterIds: readonly string[];
  /** Σ word_count over exactly those chapters (cost transparency). */
  readonly wordCount: number;
  /** Start the bulk extraction over `chapterIds` (parent mounts the panel). */
  readonly onStart: () => void;
  /** Clear the sessionStorage flag and hide the banner. */
  readonly onDismiss: () => void;
}

export function ImportSuggestExtractBanner({
  chapterIds,
  wordCount,
  onStart,
  onDismiss,
}: ImportSuggestExtractBannerProps) {
  const t = useTranslations("importing.suggestExtract");

  return (
    <div
      data-testid="import-suggest-banner"
      className="mt-2 rounded-md border border-border bg-muted/30 p-3 text-xs"
    >
      <p className="font-medium text-foreground">{t("bannerTitle")}</p>
      <p className="mt-1 text-muted-foreground">
        {t("bannerBody", { calls: chapterIds.length, words: wordCount })}
      </p>
      <div className="mt-2 flex gap-2">
        <button
          type="button"
          data-testid="import-suggest-start-btn"
          onClick={onStart}
          className="rounded bg-primary px-2 py-1 font-medium text-primary-foreground hover:opacity-90 transition-opacity"
        >
          {t("start")}
        </button>
        <button
          type="button"
          data-testid="import-suggest-dismiss-btn"
          onClick={onDismiss}
          className="rounded px-2 py-1 text-muted-foreground hover:text-foreground transition-colors"
        >
          {t("notNow")}
        </button>
      </div>
    </div>
  );
}
