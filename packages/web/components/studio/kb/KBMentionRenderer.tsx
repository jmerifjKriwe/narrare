"use client";

/**
 * Renders @Name mentions in KB body text as clickable badges.
 *
 * When ``html`` (pre-resolved by the backend) is provided, renders it
 * directly with ``dangerouslySetInnerHTML``.  Otherwise falls back to
 * plain-text parsing with local resolution data.
 */

import type { ReferenceResolution } from "@/lib/api/kb";

interface KBMentionRendererProps {
  /** Pre-resolved HTML from the backend (with <a> tags). */
  html: string | null;
  /** Raw body text (used as fallback when html is null). */
  body: string;
  /** Current novel ID for link generation. */
  novelId: string;
  /** Resolved references from the backend. */
  resolved: ReferenceResolution[];
}

export function KBMentionRenderer({ html, body, novelId, resolved }: KBMentionRendererProps) {
  if (html) {
    return (
      <div
        className="kb-mention-renderer prose prose-sm dark:prose-invert"
        // biome-ignore lint/security/noDangerouslySetInnerHtml: HTML generated server-side from @mention resolution, no user HTML passthrough
        dangerouslySetInnerHTML={{ __html: html }}
      />
    );
  }

  // Plain-text fallback — highlight @names.
  // Keys use part content directly; the regex split produces unique alternating
  // [text, mention, text, …] segments so collisions cannot occur.
  const parts = body.split(/(@[\wÀ-ÖØ-öø-ÿ][\wÀ-ÖØ-öø-ÿ\s'-]*\w)/g);
  return (
    <div className="prose prose-sm dark:prose-invert">
      {parts.map((part) => {
        if (part.startsWith("@")) {
          const mentionName = part.slice(1);
          const ref = resolved.find((r) => r.mention === mentionName && r.entry_id);
          if (ref?.slug) {
            return (
              <a
                key={`mention:${part}`}
                href={`/studio/${novelId}/kb/${ref.slug}`}
                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-primary/10 text-primary text-sm font-medium hover:bg-primary/20 transition-colors"
              >
                @{ref.entry_name}
              </a>
            );
          }
          // Unresolved mention — muted
          return (
            <span key={`unresolved:${part}`} className="text-muted-foreground/50">
              {part}
            </span>
          );
        }
        return <span key={`text:${part}`}>{part}</span>;
      })}
    </div>
  );
}
