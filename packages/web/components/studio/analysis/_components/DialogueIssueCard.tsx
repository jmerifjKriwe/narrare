"use client";

/**
 * DialogueIssueCard — one diagnosed dialogue issue.
 *
 * Renders the severity pill (Badge), the offending speaker, the diagnosis,
 * and — in analyze mode — the flagged `original_quote`. In improve mode the
 * `original_quote` is carried by each {@link DialogueAlternativeCard}'s
 * "before" block (ADR-069 Decision 9), so it is intentionally NOT duplicated
 * here: rendering it in both places would break single-target lookups and
 * clutter the card.
 *
 * Accessibility (web-design-guidelines): severity uses colour + text (never
 * colour alone); the card is a semantic `<article>`/`<header>`/`<blockquote>`
 * so heading/quote semantics are preserved; severity falls back to its raw
 * value if no translation exists.
 *
 * @module DialogueIssueCard
 */
import type { Editor } from "@tiptap/react";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import type { DialogueIssue } from "@/types";
import { DialogueAlternativeCard } from "./DialogueAlternativeCard";

interface DialogueIssueCardProps {
  issue: DialogueIssue;
  editor: Editor;
  onApplied: () => void;
}

/** Map backend severity → Badge variant. Unknown severities → secondary. */
const SEVERITY_VARIANT: Record<string, "default" | "secondary" | "destructive"> = {
  high: "destructive",
  medium: "default",
  low: "secondary",
};

/** Severities that have a dedicated i18n key; others render their raw value. */
const KNOWN_SEVERITIES = ["low", "medium", "high"] as const;

export function DialogueIssueCard({ issue, editor, onApplied }: DialogueIssueCardProps) {
  const t = useTranslations();
  const variant = SEVERITY_VARIANT[issue.severity] ?? "secondary";
  const hasAlternatives = !!issue.alternatives && issue.alternatives.length > 0;
  const severityLabel = (KNOWN_SEVERITIES as readonly string[]).includes(issue.severity)
    ? t(`dialogueCoach.severity.${issue.severity}`)
    : issue.severity;

  return (
    <article className="border border-border rounded-lg p-4 space-y-2 bg-card">
      <header className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <Badge variant={variant}>{severityLabel}</Badge>
          <span className="text-sm font-medium truncate">{issue.issue_type}</span>
        </div>
        {issue.speaker && (
          <span className="text-xs text-muted-foreground flex-shrink-0">{issue.speaker}</span>
        )}
      </header>

      {/* In analyze mode (no alternatives) the flagged quote is the main
          evidence; in improve mode each alternative shows it as the "before". */}
      {!hasAlternatives && (
        <blockquote className="text-sm italic text-muted-foreground border-l-2 border-border pl-2">
          {issue.original_quote}
        </blockquote>
      )}

      <p className="text-sm">{issue.diagnosis}</p>

      {issue.alternatives?.map((alt) => (
        <DialogueAlternativeCard
          key={`${alt.rewrite}|${alt.explanation}`}
          alternative={alt}
          originalQuote={issue.original_quote}
          editor={editor}
          onApplied={onApplied}
        />
      ))}
    </article>
  );
}
