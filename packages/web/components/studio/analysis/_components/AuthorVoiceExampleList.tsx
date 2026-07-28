/**
 * AuthorVoiceExampleList — renders the curated representative prose passages
 * (ANAL-007 `author_examples`).
 *
 * These ARE rendered into {{author_voice}} by the Core
 * `render_author_voice_for_generation` (the descriptive side of the
 * descriptive/metric boundary, ADR-074). The passages are the exemplars of
 * the writer's narrative voice — distinct from per-character voice_examples.
 *
 * Extracted per RULE-04.
 */

interface AuthorVoiceExampleListProps {
  examples: string[] | null | undefined;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}

export function AuthorVoiceExampleList({ examples, t }: AuthorVoiceExampleListProps) {
  if (!examples || examples.length === 0) return null;

  return (
    <section className="rounded-lg border border-border p-4 bg-card">
      <h4 className="text-xs text-muted-foreground mb-2 font-medium">
        {t("authorVoice.authorExamples")}
      </h4>
      <div className="space-y-1">
        {examples.map((passage) => (
          <blockquote
            key={passage}
            className="border-l-2 border-violet-300 dark:border-violet-700 pl-2 text-sm italic text-muted-foreground"
          >
            {passage}
          </blockquote>
        ))}
      </div>
    </section>
  );
}
