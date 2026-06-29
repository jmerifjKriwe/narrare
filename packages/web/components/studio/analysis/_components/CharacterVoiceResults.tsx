/**
 * CharacterVoiceResults — renders the per-character voice-profile results list.
 *
 * Empty state → no-results message. Otherwise maps each
 * {@link CharacterVoiceResult} to a {@link CharacterVoiceResultCard}.
 *
 * Extracted from {@link ../CharacterVoicePanel} per RULE-04 (file-size limit).
 */

import type { CharacterVoiceResult } from "@/lib/api/character-voice-stream";
import { CharacterVoiceResultCard } from "./CharacterVoiceResultCard";

interface CharacterVoiceResultsProps {
  results: CharacterVoiceResult[];
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}

export function CharacterVoiceResults({ results, t }: CharacterVoiceResultsProps) {
  if (results.length === 0) {
    return <p className="text-sm text-muted-foreground">{t("characterVoice.noResults")}</p>;
  }

  return (
    <div className="space-y-4">
      {results.map((result) => (
        <CharacterVoiceResultCard
          key={`${result.character_name}-${result.kb_entry_id ?? "no-kb"}`}
          result={result}
          t={t}
        />
      ))}
    </div>
  );
}
