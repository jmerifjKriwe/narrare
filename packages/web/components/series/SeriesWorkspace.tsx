"use client";

/**
 * SeriesWorkspace — persistent shell for the /series/[id]/* routes
 * (Spec 1, Slice 4, Task 4.6).
 *
 * Responsibilities:
 *   - Fetch the Series via `useSeries(seriesId)` and render loading / error
 *     states (quality bar §error-states).
 *   - Compose the workspace from focused sub-components (RULE-04):
 *       SeriesHero    — series header (title, badges, status, meta).
 *       SeriesTabNav  — 4-tab segment-based navigation.
 *   - Render the matched route page (`children`) inside a `PhaseCrossfade`
 *     keyed by pathname, so tab switches crossfade instead of hard-cutting.
 *
 * Architecture notes:
 *   - Server `layout.tsx` extracts `params.id` and passes it here as
 *     `seriesId`; this client component owns the data fetch + composition.
 *   - All copy goes through `useTranslations("studio")` — no hardcoded JSX
 *     text (enforced by scripts/validate-i18n.ts).
 *   - motion/react is used only via the shared `PhaseCrossfade`; reduced-motion
 *     is respected globally by the MotionProvider.
 */
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { SeriesHero } from "@/components/series/SeriesHero";
import { SeriesTabNav } from "@/components/series/SeriesTabNav";
import { PhaseCrossfade } from "@/components/ui/phase-crossfade";
import { useSeries } from "@/lib/hooks/useSeries";

interface SeriesWorkspaceProps {
  readonly seriesId: string;
  readonly children: React.ReactNode;
}

export function SeriesWorkspace({ seriesId, children }: SeriesWorkspaceProps) {
  const t = useTranslations("studio");
  const pathname = usePathname();
  const { data: series, isLoading, isError } = useSeries(seriesId);

  if (isLoading) {
    return (
      <div
        data-testid="series-workspace-loading"
        className="flex min-h-screen items-center justify-center bg-background"
      >
        <span className="text-muted-foreground">{t("series.workspace.loading")}</span>
      </div>
    );
  }

  if (isError || !series) {
    return (
      <div
        data-testid="series-workspace-error"
        className="flex min-h-screen items-center justify-center bg-background"
      >
        <span className="text-muted-foreground">{t("series.workspace.notFound")}</span>
      </div>
    );
  }

  return (
    <div data-testid="series-workspace" className="flex min-h-screen flex-col bg-background">
      <SeriesHero series={series} />
      <SeriesTabNav seriesId={seriesId} pathname={pathname} />

      {/* Tab content — crossfades between routes on pathname change. */}
      <main className="flex-1 overflow-y-auto p-6">
        <PhaseCrossfade phase={pathname}>{children}</PhaseCrossfade>
      </main>
    </div>
  );
}
