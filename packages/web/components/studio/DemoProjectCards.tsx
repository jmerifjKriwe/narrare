"use client";

import { useQuery } from "@tanstack/react-query";
import { BookOpen, Globe, RefreshCw, Users } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { setupApi } from "@/lib/api/client";
import type { DemoProjectInfo } from "@/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DemoProjectCardsProps {
  /** Optional: show even when the user already has novels (default: true) */
  readonly forceShow?: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * DemoProjectCards — Grid of demo project cards for the dashboard.
 *
 * Fetches demos via setupApi.listDemos(), displays loading/error/empty states.
 * RULE-04: extracted from DashboardView to keep file size under limit.
 */
export function DemoProjectCards(_props?: DemoProjectCardsProps) {
  const t = useTranslations("studio");
  const router = useRouter();

  const {
    data: demos = [],
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["demos"],
    queryFn: setupApi.listDemos,
  });

  // Don't render section if no demos and not loading
  if (!isLoading && !isError && demos.length === 0) return null;

  return (
    <section aria-label={t("demos.title")}>
      <div className="mb-4">
        <h2 className="text-xl font-medium mb-1">{t("demos.title")}</h2>
        <p className="text-sm text-muted-foreground">{t("demos.subtitle")}</p>
      </div>

      {isLoading && <DemoSkeletonGrid />}
      {isError && <DemoErrorState onRetry={() => refetch()} />}
      {!isLoading && !isError && demos.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {demos.map((demo) => (
            <DemoCard key={demo.id} demo={demo} onSelect={handleSelect} />
          ))}
        </div>
      )}
    </section>
  );

  function handleSelect(demo: DemoProjectInfo) {
    router.push(`/wizard?starter=${demo.id}`);
  }
}

// ---------------------------------------------------------------------------
// Sub-components (RULE-04: keep DemoProjectCards under 200 lines)
// ---------------------------------------------------------------------------

function DemoCard({
  demo,
  onSelect,
}: {
  readonly demo: DemoProjectInfo;
  readonly onSelect: (demo: DemoProjectInfo) => void;
}) {
  const t = useTranslations("studio");

  return (
    <button
      type="button"
      onClick={() => onSelect(demo)}
      className="group text-left bg-card border border-border rounded-lg p-6 hover:shadow-md transition-shadow"
    >
      <h3 className="text-lg font-medium mb-1">{demo.title}</h3>

      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs px-2 py-0.5 bg-muted rounded-md text-muted-foreground">
          {demo.genre}
        </span>
        <span className="flex items-center gap-1 text-xs text-muted-foreground">
          <Globe className="w-3 h-3" />
          {demo.writing_language}
        </span>
      </div>

      <p className="text-sm text-muted-foreground mb-4 line-clamp-2">{demo.description}</p>

      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <span>{t("demos.chapters", { count: demo.chapter_count })}</span>
        <span>{t("demos.words", { count: demo.word_count })}</span>
        <span className="flex items-center gap-1">
          <Users className="w-3 h-3" />
          {t("demos.characters", { count: demo.character_count })}
        </span>
      </div>

      <div className="mt-4 text-sm font-medium text-primary opacity-0 group-hover:opacity-100 transition-opacity">
        {t("demos.loadDemo")} →
      </div>
    </button>
  );
}

function DemoSkeletonGrid() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {[1, 2, 3].map((i) => (
        <div key={i} className="bg-card border border-border rounded-lg p-6 animate-pulse">
          <div className="h-6 bg-muted rounded mb-2 w-3/4" />
          <div className="flex gap-2 mb-3">
            <div className="h-5 bg-muted rounded w-16" />
            <div className="h-5 bg-muted rounded w-12" />
          </div>
          <div className="h-4 bg-muted rounded mb-2 w-full" />
          <div className="h-4 bg-muted rounded mb-4 w-2/3" />
          <div className="flex gap-4">
            <div className="h-4 bg-muted rounded w-16" />
            <div className="h-4 bg-muted rounded w-16" />
            <div className="h-4 bg-muted rounded w-20" />
          </div>
        </div>
      ))}
    </div>
  );
}

function DemoErrorState({ onRetry }: { readonly onRetry: () => void }) {
  const t = useTranslations("studio");

  return (
    <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
      <BookOpen className="w-12 h-12 mb-3 opacity-10" />
      <p className="text-sm mb-3">{t("demos.error")}</p>
      <button
        type="button"
        onClick={onRetry}
        className="flex items-center gap-2 px-4 py-2 text-sm border border-border rounded-lg hover:bg-accent transition-colors"
      >
        <RefreshCw className="w-4 h-4" />
        {t("demos.retry")}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Skeleton loader for the initial page load (re-exported for DashboardView)
// ---------------------------------------------------------------------------

export function DemoSectionSkeleton() {
  return (
    <section aria-label="Demo projects loading">
      <div className="mb-4">
        <div className="h-7 bg-muted rounded w-40 mb-2 animate-pulse" />
        <div className="h-4 bg-muted rounded w-64 animate-pulse" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-card border border-border rounded-lg p-6 animate-pulse">
            <div className="h-6 bg-muted rounded mb-2 w-3/4" />
            <div className="flex gap-2 mb-3">
              <div className="h-5 bg-muted rounded w-16" />
              <div className="h-5 bg-muted rounded w-12" />
            </div>
            <div className="h-4 bg-muted rounded mb-2 w-full" />
            <div className="h-4 bg-muted rounded w-2/3" />
          </div>
        ))}
      </div>
    </section>
  );
}
