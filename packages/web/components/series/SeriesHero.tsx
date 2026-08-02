"use client";

/**
 * SeriesHero — compact hero header for the Series workspace (Spec 1, Slice 4).
 *
 * Identifies the Series (title, status, subtitle, genre, planned novel count)
 * and provides the back-to-dashboard link. Extracted from SeriesWorkspace
 * (RULE-04: one responsibility per file). All copy goes through
 * `useTranslations("studio")` — no hardcoded JSX text (enforced by
 * scripts/validate-i18n.ts).
 */
import Link from "next/link";
import { useTranslations } from "next-intl";
import type { Series } from "@/types";

interface SeriesHeroProps {
  readonly series: Series;
}

export function SeriesHero({ series }: SeriesHeroProps) {
  const t = useTranslations("studio");

  return (
    <header data-testid="series-hero" className="border-b bg-accent-series-muted px-6 py-6">
      <Link
        href="/"
        className="mb-3 inline-block text-sm text-muted-foreground hover:text-foreground"
      >
        {t("series.workspace.backToDashboard")}
      </Link>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="inline-block rounded-md bg-accent-series px-2 py-0.5 text-xs text-accent-series-foreground">
          {t("series.workspace.badgeSeries")}
        </span>
        <span className="inline-block rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
          {t(`series.workspace.status.${series.status}`)}
        </span>
      </div>
      <h1 className="text-2xl font-medium">{series.title}</h1>
      {series.subtitle ? <p className="mt-1 text-muted-foreground">{series.subtitle}</p> : null}
      {(series.genre ?? series.planned_novel_count) ? (
        <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground">
          {series.genre ? (
            <span>
              <strong className="font-medium text-foreground">{t("series.workspace.genre")}</strong>
              {": "}
              {series.genre}
            </span>
          ) : null}
          {series.planned_novel_count ? (
            <span>
              <strong className="font-medium text-foreground">
                {t("series.workspace.planned")}
              </strong>
              {": "}
              {series.planned_novel_count}
            </span>
          ) : null}
        </div>
      ) : null}
    </header>
  );
}
