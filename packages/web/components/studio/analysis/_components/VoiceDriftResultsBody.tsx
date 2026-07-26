/**
 * VoiceDriftResultsBody — the results branch of {@link ../VoiceDriftPanel}.
 *
 * Renders the heatmap overview + band legend when there are analysable
 * characters, the graceful no-profile skip list (RULE-11) when characters
 * could not be analysed, and an empty state when no characters have profiles.
 *
 * Extracted from the panel per RULE-04 (file-size limit).
 *
 * @module VoiceDriftResultsBody
 */

import type { VoiceDriftCharacterResult, VoiceDriftNoProfile } from "@/lib/api/voice-drift-stream";
import { VoiceDriftBandLegend } from "./VoiceDriftBandLegend";
import { VoiceDriftOverview } from "./VoiceDriftOverview";

interface VoiceDriftResultsBodyProps {
  results: VoiceDriftCharacterResult[] | null;
  noProfile: VoiceDriftNoProfile[] | null;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}

export function VoiceDriftResultsBody({ results, noProfile, t }: VoiceDriftResultsBodyProps) {
  const hasResults = (results?.length ?? 0) > 0;
  const hasNoProfile = (noProfile?.length ?? 0) > 0;

  if (!hasResults && !hasNoProfile) {
    return <p className="text-sm text-muted-foreground">{t("voiceDrift.noProfiledCharacters")}</p>;
  }

  return (
    <>
      {hasResults && (
        <>
          <VoiceDriftOverview results={results!} t={t} />
          <VoiceDriftBandLegend t={t} />
        </>
      )}
      {hasNoProfile && (
        <div className="rounded-lg border border-border bg-muted/20 p-3">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            {t("voiceDrift.skippedCharacters")}
          </p>
          <ul className="space-y-1">
            {noProfile!.map((skip) => (
              <li
                key={`${skip.character_id || skip.character_name}`}
                className="text-sm text-muted-foreground"
              >
                <span className="font-medium text-foreground">
                  {skip.character_name || "\u2014"}
                </span>
                {" \u2014 "}
                <span>{t(`voiceDrift.noProfileReason.${skip.reason}`)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}
