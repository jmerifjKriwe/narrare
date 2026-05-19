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

  return (
    <div className="prose prose-sm dark:prose-invert">
      {renderPlainTextMentions(body, novelId, resolved)}
    </div>
  );
}

/**
 * Resolve mention patterns in plain-text body using the resolved array.
 *
 * Algorithm: scan for `@` positions, then try to match against resolved
 * mentions (longest first) to support multi-word names like `@Anna Müller`.
 * If no resolved match, try a single-word regex for unresolved mentions.
 */
function renderPlainTextMentions(
  body: string,
  novelId: string,
  resolved: ReferenceResolution[],
): React.ReactNode[] {
  // Pre-sort resolved mentions by mention length descending to match longest first
  const sortedResolved = [...resolved]
    .filter((r) => r.entry_id && r.slug)
    .sort((a, b) => b.mention.length - a.mention.length);

  // Single-word mention regex (no spaces) for unresolved @names
  const singleWordRe = /^@([\wÀ-ÖØ-öø-ÿ](?:[\wÀ-ÖØ-öø-ÿ'-]*[\wÀ-ÖØ-öø-ÿ])?)/;

  const parts: React.ReactNode[] = [];
  let keyIdx = 0;
  let i = 0;

  while (i < body.length) {
    const atIdx = body.indexOf("@", i);

    if (atIdx === -1) {
      // No more @ signs — emit remaining text
      if (i < body.length) {
        parts.push(<span key={`t${keyIdx++}`}>{body.slice(i)}</span>);
      }
      break;
    }

    // Emit text before the @
    if (atIdx > i) {
      parts.push(<span key={`t${keyIdx++}`}>{body.slice(i, atIdx)}</span>);
    }

    const afterAt = body.slice(atIdx + 1);

    // 1. Try to match a resolved mention (longest first)
    let matched = false;
    for (const ref of sortedResolved) {
      if (afterAt.startsWith(ref.mention)) {
        // Word boundary: next char after mention must not be a word char
        const nextChar = afterAt[ref.mention.length];
        if (!nextChar || !/[\wÀ-ÖØ-öø-ÿ]/.test(nextChar)) {
          parts.push(
            <a
              key={`m${keyIdx++}`}
              href={`/studio/${novelId}/kb/${ref.slug}`}
              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-primary/10 text-primary text-sm font-medium hover:bg-primary/20 transition-colors"
            >
              @{ref.entry_name}
            </a>,
          );
          i = atIdx + 1 + ref.mention.length;
          matched = true;
          break;
        }
      }
    }

    if (matched) continue;

    // 2. Try single-word unresolved mention
    const wordMatch = singleWordRe.exec(body.slice(atIdx));
    if (wordMatch) {
      parts.push(
        <span key={`u${keyIdx++}`} className="text-muted-foreground/50">
          {wordMatch[0]}
        </span>,
      );
      i = atIdx + wordMatch[0].length;
      continue;
    }

    // 3. Lone @ not followed by a valid name — emit as literal text
    parts.push(<span key={`t${keyIdx++}`}>@</span>);
    i = atIdx + 1;
  }

  return parts;
}
