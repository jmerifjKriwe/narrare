"use client";

import { useTranslations } from "next-intl";
import type { PreferenceProfile as PreferenceProfileType } from "@/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PreferenceProfileProps {
  readonly profile: PreferenceProfileType;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Confidence badge — color varies by score. */
function ConfidenceBadge({ confidence }: { readonly confidence: number }) {
  const t = useTranslations("studio");
  const pct = Math.round(confidence * 100);

  let badgeClass: string;
  if (pct >= 70) {
    badgeClass = "bg-green-500/15 text-green-700 dark:text-green-400";
  } else if (pct >= 40) {
    badgeClass = "bg-yellow-500/15 text-yellow-700 dark:text-yellow-400";
  } else {
    badgeClass = "bg-red-500/15 text-red-700 dark:text-red-400";
  }

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${badgeClass}`}
    >
      {t("learning.confidence", { score: pct })}
    </span>
  );
}

/** A single pattern section. */
function PatternSection({ title, items }: { readonly title: string; readonly items: string[] }) {
  if (items.length === 0) return null;

  return (
    <div className="space-y-1.5">
      <h4 className="text-sm font-medium text-foreground">{title}</h4>
      <ul className="space-y-1">
        {items.map((item) => (
          <li key={item} className="flex items-start gap-2 text-xs text-muted-foreground">
            <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-primary/60 flex-shrink-0" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function PreferenceProfile({ profile }: PreferenceProfileProps) {
  const t = useTranslations("studio");

  const stylePatterns = Object.entries(profile.style).map(([key, value]) => `${key}: ${value}`);
  const contentPatterns = Object.entries(profile.content).map(([key, value]) => `${key}: ${value}`);
  const avoidancePatterns = profile.constraints;

  const hasAnyData =
    stylePatterns.length > 0 || contentPatterns.length > 0 || avoidancePatterns.length > 0;

  if (!hasAnyData) {
    return (
      <div className="text-sm text-muted-foreground py-4 text-center">
        {t("learning.profileEmpty")}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header with confidence */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          {t("learning.statusInteractions", { count: profile.event_count })}
        </span>
        <ConfidenceBadge confidence={profile.confidence} />
      </div>

      {/* Pattern sections */}
      <PatternSection title={t("learning.stylePatterns")} items={stylePatterns} />
      <PatternSection title={t("learning.contentPatterns")} items={contentPatterns} />
      <PatternSection title={t("learning.avoidancePatterns")} items={avoidancePatterns} />
    </div>
  );
}
