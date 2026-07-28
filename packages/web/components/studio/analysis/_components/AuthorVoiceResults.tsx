/**
 * AuthorVoiceResults — orchestrator for the results view of the AuthorVoicePanel
 * (ANAL-007). Composes the descriptive summary, curated examples, last-analyzed
 * freshness row, and the collapsible advanced-metrics section.
 *
 * Extracted from {@link ../AuthorVoicePanel} per RULE-04 (file-size limit).
 */

import type { AuthorVoiceResult } from "@/lib/api/author-voice-stream";
import { AuthorVoiceAdvancedMetrics } from "./AuthorVoiceAdvancedMetrics";
import { AuthorVoiceDescriptiveSummary } from "./AuthorVoiceDescriptiveSummary";
import { AuthorVoiceExampleList } from "./AuthorVoiceExampleList";

interface AuthorVoiceResultsProps {
  result: AuthorVoiceResult;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}

export function AuthorVoiceResults({ result, t }: AuthorVoiceResultsProps) {
  const profile = result.profile;
  if (!profile) {
    return <p className="text-sm text-muted-foreground">{t("authorVoice.noProfile")}</p>;
  }

  const updatedAt = profile.updated_at ?? null;
  const freshnessLabel =
    profile.is_fresh === false ? t("authorVoice.stale") : t("authorVoice.fresh");

  return (
    <div className="space-y-4">
      {/* Last-analyzed timestamp + freshness indicator */}
      <p className="text-xs text-muted-foreground flex items-center justify-between">
        <span>
          {updatedAt
            ? t("authorVoice.lastAnalyzed", { date: updatedAt })
            : t("authorVoice.neverAnalyzed")}
        </span>
        <span className="text-[11px] uppercase tracking-wide">{freshnessLabel}</span>
      </p>

      <AuthorVoiceDescriptiveSummary profile={profile} t={t} />
      <AuthorVoiceExampleList examples={profile.author_examples} t={t} />
      <AuthorVoiceAdvancedMetrics profile={profile} t={t} />
    </div>
  );
}
