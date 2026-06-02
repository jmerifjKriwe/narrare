"use client";

/**
 * PromptPreview — Renders a prompt template with variables substituted.
 *
 * Shows {{variables}} replaced by example values where available.
 * Unknown variables are highlighted with an amber background.
 * Extracted from PromptEditor per RULE-04.
 */

interface PromptPreviewProps {
  readonly content: string;
  readonly variables: readonly string[];
}

/** Example values for common variable names. */
const EXAMPLE_VALUES: Record<string, string> = {
  // Character names
  character_name: "Elena Vance",
  protagonist: "Elena Vance",
  name: "Elena Vance",
  char_name: "Elena Vance",
  // Chapter / story
  chapter_title: "Kapitel 1: Der Anfang",
  chapter_name: "Kapitel 1: Der Anfang",
  title: "Kapitel 1: Der Anfang",
  // Genre / style
  genre: "Fantasy",
  style: "Erzählend",
  tone: "Düster",
  // Context
  setting: "Das Königreich Aethermoor",
  location: "Die Schwarze Zitadelle",
  scene: "Die Thronsaal-Szene",
  context: "Die Protagonistin betritt den Thronsaal",
  // Content
  topic: "Magie",
  theme: "Verrat und Erlösung",
  plot_point: "Die Entdeckung des verbotenen Buches",
  summary: "Eine Zusammenfassung der bisherigen Handlung",
  excerpt: "Der Textauszug aus dem aktuellen Kapitel",
  // Narrative
  pov: "Dritte Person",
  perspective: "Ich-Erzähler",
  tense: "Präteritum",
  // World-building
  world_name: "Aethermoor",
  faction: "Der Silberne Orden",
  era: "Das Zeitalter des Erwachens",
  language: "Gemeinsprache",
};

/**
 * Renders prompt content with variable substitution.
 * Known variables get their example value; unknown ones are highlighted.
 */
export function PromptPreview({ content }: PromptPreviewProps) {
  // Build a regex that matches all {{variable}} patterns
  const varPattern = /\{\{(\w+)\}\}/g;

  // Split content into segments of text and variable references
  const segments: Array<{ type: "text" | "variable"; value: string; key: string }> = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null = varPattern.exec(content);
  let segIdx = 0;

  while (match !== null) {
    // Text before the variable
    if (match.index > lastIndex) {
      segments.push({
        type: "text",
        value: content.slice(lastIndex, match.index),
        key: `t-${segIdx++}`,
      });
    }
    segments.push({ type: "variable", value: match[1], key: `v-${segIdx++}` });
    lastIndex = match.index + match[0].length;
    match = varPattern.exec(content);
  }
  // Remaining text after last variable
  if (lastIndex < content.length) {
    segments.push({ type: "text", value: content.slice(lastIndex), key: `t-${segIdx++}` });
  }

  return (
    <div className="w-full min-h-[400px] px-4 py-3 border border-border rounded-md bg-background text-sm font-mono whitespace-pre-wrap overflow-auto">
      {segments.map((segment) => {
        if (segment.type === "text") {
          return <span key={segment.key}>{segment.value}</span>;
        }
        // Variable — substitute with example or highlight
        const exampleValue = EXAMPLE_VALUES[segment.value];
        if (exampleValue) {
          return (
            <span key={segment.key} className="text-primary font-semibold">
              {exampleValue}
            </span>
          );
        }
        // Unknown variable — highlight
        return (
          <span key={segment.key} className="bg-amber-100 dark:bg-amber-900/30 px-1 rounded">
            {`{{${segment.value}}}`}
          </span>
        );
      })}
    </div>
  );
}
