"use client";

/** AdaptiveDashboard — LEARN-002 settings surface (ADR-069 Decision 12/15).
 *
 *  Composes the enable toggle, the 4 weight sliders, and the source summary.
 *  All state flows through the canonical TanStack Query key (Decision 15):
 *  mutations invalidate `["adaptive-context", projectId]`, so the editor
 *  Status Indicator and the Dialogue Coach panel refetch in lockstep. */
import { Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import {
  useAdaptiveContext,
  useSetAdaptiveWeights,
  useToggleAdaptive,
} from "@/lib/hooks/useAdaptiveContext";
import { AdaptiveSnapshotHistory } from "./_components/AdaptiveSnapshotHistory";
import { AdaptiveSourceList } from "./_components/AdaptiveSourceList";
import { AdaptiveToggle } from "./_components/AdaptiveToggle";
import { AdaptiveWeightSliders } from "./_components/AdaptiveWeightSliders";

export function AdaptiveDashboard({ novelId }: { readonly novelId: string }) {
  const t = useTranslations("adaptive");
  const { data, isLoading, error } = useAdaptiveContext(novelId);
  const toggle = useToggleAdaptive(novelId);
  const setWeights = useSetAdaptiveWeights(novelId);

  if (isLoading) {
    return (
      <div className="motion-safe:animate-pulse text-sm text-muted-foreground">{t("loading")}</div>
    );
  }
  if (error || !data) {
    return (
      <div className="text-sm text-destructive" role="alert">
        {t("loadFailed")}
      </div>
    );
  }

  return (
    <section className="bg-card border border-border rounded-lg p-6 space-y-6">
      <div className="flex items-center gap-2">
        <Sparkles className="w-5 h-5 text-violet-500" />
        <h3 className="text-lg font-medium">{t("title")}</h3>
      </div>
      <AdaptiveToggle
        enabled={data.enabled}
        onToggle={(next) => toggle.mutate(next)}
        pending={toggle.isPending}
      />
      <AdaptiveWeightSliders
        weights={data.weights}
        onCommit={(next) => setWeights.mutate(next)}
        pending={setWeights.isPending}
      />
      <AdaptiveSourceList sources={data.sources} hasAnySignal={data.has_any_signal} />
      <AdaptiveSnapshotHistory projectId={novelId} />
    </section>
  );
}
