"use client";

import { useTranslations } from "next-intl";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface LearningStatusProps {
  /** Number of feedback events collected so far. */
  readonly eventCount: number;
  /** Target number of events for "full" learning tier (default: 50). */
  readonly target?: number;
  /** Whether the parent wants compact (badge) or expanded display. */
  readonly compact?: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function LearningStatus({ eventCount, target = 50, compact = false }: LearningStatusProps) {
  const t = useTranslations("studio");
  const pct = Math.min(100, Math.round((eventCount / target) * 100));

  // Determine tier label
  let tierLabel: string;
  let tierColor: string;
  if (eventCount < 5) {
    tierLabel = t("learning.tierCollecting");
    tierColor = "bg-muted text-muted-foreground";
  } else if (eventCount < 20) {
    tierLabel = t("learning.tierEmerging");
    tierColor = "bg-yellow-500/15 text-yellow-700 dark:text-yellow-400";
  } else if (eventCount < 50) {
    tierLabel = t("learning.tierGrowing");
    tierColor = "bg-blue-500/15 text-blue-700 dark:text-blue-400";
  } else {
    tierLabel = t("learning.tierEstablished");
    tierColor = "bg-green-500/15 text-green-700 dark:text-green-400";
  }

  if (compact) {
    return (
      <span
        className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${tierColor}`}
        title={t("learning.statusInteractions", { count: eventCount })}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-current opacity-60" />
        <span>{t("learning.statusInteractions", { count: eventCount })}</span>
      </span>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-foreground">{t("learning.progressLabel")}</span>
        <span className="text-xs text-muted-foreground">
          {t("learning.statusInteractions", { count: eventCount })}
        </span>
      </div>

      {/* Progress bar */}
      <div className="w-full h-2 bg-accent rounded-full overflow-hidden">
        <div
          className="h-full bg-primary rounded-full transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Tier badge */}
      <div className="flex items-center gap-2">
        <span
          className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${tierColor}`}
        >
          {tierLabel}
        </span>
      </div>
    </div>
  );
}
