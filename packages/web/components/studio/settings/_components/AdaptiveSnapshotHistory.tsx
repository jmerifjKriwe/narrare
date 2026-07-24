"use client";

/** AdaptiveSnapshotHistory — recent adaptive activity timeline (ADR-070 endpoint A).
 *
 *  Renders a vertical timeline of the most recent adaptive invocations for the
 *  project: when they ran, which weights were active, and which signal sources
 *  shaped them. Newest first (defensively sorted — the contract does not
 *  guarantee server-side ordering). History is supplementary, so it degrades
 *  gracefully to the empty state on error rather than blocking the dashboard. */
import { useTranslations } from "next-intl";
import { useAdaptiveSnapshots } from "@/lib/hooks/useAdaptiveSnapshots";
import type { AdaptiveSnapshotItem } from "@/types";

const WEIGHT_KEYS = ["preference", "voice_fidelity", "style_constraints", "avoidance"] as const;

export function AdaptiveSnapshotHistory({ projectId }: { readonly projectId: string }) {
  const t = useTranslations("adaptive");
  const tAi = useTranslations("aiAssist");
  const { data, isLoading, error } = useAdaptiveSnapshots(projectId);

  if (isLoading) {
    return (
      <p className="text-sm text-muted-foreground motion-safe:animate-pulse">{t("loading")}</p>
    );
  }
  // History is non-critical — on error or absence, show the empty state, never block.
  if (error || !data || data.items.length === 0) {
    return <p className="text-sm text-muted-foreground">{tAi("historyEmpty")}</p>;
  }

  // Newest first (js-tosorted-immutable — does not mutate the cached query data).
  const items = data.items.toSorted(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );

  return (
    <div className="space-y-3">
      <p className="font-medium">{t("history.title")}</p>
      <ol className="space-y-3">
        {items.map((item, index) => (
          <SnapshotRow key={item.invocation_id ?? `${item.created_at}-${index}`} item={item} />
        ))}
      </ol>
    </div>
  );
}

function SnapshotRow({ item }: { readonly item: AdaptiveSnapshotItem }) {
  const t = useTranslations("adaptive");
  const weights = item.weights;
  const activeSources = item.source_summary
    ? Object.entries(item.source_summary)
        .filter(([, value]) => value.trim() !== "")
        .map(([key]) => key)
    : [];

  return (
    <li className="border-l-2 border-border pl-3 space-y-1.5">
      <time dateTime={item.created_at} className="block text-xs text-muted-foreground">
        {formatTimestamp(item.created_at)}
      </time>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
        <span data-testid="snapshot-intent" className="font-medium">
          {item.intent}
        </span>
        {item.mode ? (
          <span className="text-xs text-muted-foreground">
            {t("history.mode")}: {item.mode}
          </span>
        ) : null}
      </div>
      {weights ? (
        <div className="space-y-0.5">
          <p className="text-xs text-muted-foreground">{t("history.weights")}</p>
          <dl className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs">
            {WEIGHT_KEYS.map((key) => (
              <div key={key} className="flex justify-between gap-2">
                <dt className="text-muted-foreground">{t(`weight.${key}`)}</dt>
                <dd>{weights[key].toFixed(2)}</dd>
              </div>
            ))}
          </dl>
        </div>
      ) : null}
      {activeSources.length > 0 ? (
        <div className="space-y-0.5">
          <p className="text-xs text-muted-foreground">{t("history.sources")}</p>
          <ul className="flex flex-wrap gap-1.5">
            {activeSources.map((src) => (
              <li key={src} className="rounded bg-muted px-1.5 py-0.5 text-xs">
                {src}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </li>
  );
}

function formatTimestamp(iso: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(iso),
  );
}
