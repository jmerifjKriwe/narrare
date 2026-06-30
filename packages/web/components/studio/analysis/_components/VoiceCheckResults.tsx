/**
 * VoiceCheckResults — renders the per-character voice-check results list.
 *
 * Empty state → no-results message (no speaking characters / no dialogue).
 * Otherwise maps each {@link VoiceCheckResult} to a {@link VoiceCheckResultCard}.
 *
 * Extracted from {@link ../VoiceCheckPanel} per RULE-04 (file-size limit).
 */

import type { VoiceCheckResult } from "@/lib/api/voice-check-stream";
import { VoiceCheckResultCard } from "./VoiceCheckResultCard";

interface VoiceCheckResultsProps {
  results: VoiceCheckResult[];
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}

export function VoiceCheckResults({ results, t }: VoiceCheckResultsProps) {
  if (results.length === 0) {
    return <p className="text-sm text-muted-foreground">{t("voiceCheck.noResults")}</p>;
  }

  return (
    <div className="space-y-4">
      {results.map((result) => (
        <VoiceCheckResultCard
          key={`${result.character_name}-${result.has_profile ? "profile" : "no-profile"}`}
          result={result}
          t={t}
        />
      ))}
    </div>
  );
}
