/**
 * AuthorVoiceDriftResults — the results branch of {@link ../AuthorVoiceDriftPanel}.
 *
 * Renders the singular narrator trend + band legend when a result is present,
 * or the graceful no-profile message (RULE-11) when the narrator could not be
 * analysed. Author voice is ONE narrator per novel, so exactly one of these
 * branches applies (contrast Phase 1's analysable-list + skip-list composite).
 *
 * Extracted from the panel per RULE-04 (file-size limit).
 *
 * @module AuthorVoiceDriftResults
 */

import type {
  AuthorVoiceDriftNoProfile,
  AuthorVoiceDriftResult,
} from "@/lib/api/author-voice-drift-stream";
import { AuthorVoiceDriftTrend } from "./AuthorVoiceDriftTrend";
import { VoiceDriftBandLegend } from "./VoiceDriftBandLegend";

interface AuthorVoiceDriftResultsProps {
  result: AuthorVoiceDriftResult | null;
  noProfile: AuthorVoiceDriftNoProfile | null;
  /** scoped `analysis` translator. */
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}

export function AuthorVoiceDriftResults({ result, noProfile, t }: AuthorVoiceDriftResultsProps) {
  if (result) {
    return (
      <>
        <AuthorVoiceDriftTrend result={result} t={t} />
        <VoiceDriftBandLegend t={t} />
      </>
    );
  }

  // Graceful no-profile skip (RULE-11). Author voice is one narrator per novel,
  // so the skip carries only a reason (no character identity).
  return (
    <div className="rounded-lg border border-border bg-muted/20 p-4">
      <p className="mb-1 text-base font-medium text-foreground">
        {t("authorVoiceDrift.noProfileTitle")}
      </p>
      <p className="text-sm text-muted-foreground">
        {t(`authorVoiceDrift.noProfileReason.${noProfile?.reason ?? "no_stored_profile"}`)}
      </p>
      <p className="mt-2 text-sm text-muted-foreground">{t("authorVoiceDrift.noProfileHint")}</p>
    </div>
  );
}
