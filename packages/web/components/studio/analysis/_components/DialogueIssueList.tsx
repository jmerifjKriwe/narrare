"use client";

/**
 * DialogueIssueList — maps the coach's `issues[]` to cards + empty state.
 *
 * Thin list container (RULE-06: one responsibility — ordering + empty state);
 * each issue renders via {@link DialogueIssueCard}. Keys are content-derived
 * (original_quote + diagnosis) rather than array indices, so reordering or
 * partial updates don't thrash React reconciliation.
 *
 * @module DialogueIssueList
 */
import type { Editor } from "@tiptap/react";
import { useTranslations } from "next-intl";
import type { DialogueIssue } from "@/types";
import { DialogueIssueCard } from "./DialogueIssueCard";

interface DialogueIssueListProps {
  issues: DialogueIssue[];
  editor: Editor;
  onApplied: () => void;
}

export function DialogueIssueList({ issues, editor, onApplied }: DialogueIssueListProps) {
  const t = useTranslations();
  if (issues.length === 0) {
    return (
      <p className="text-sm text-muted-foreground text-center py-8">
        {t("dialogueCoach.noIssues")}
      </p>
    );
  }
  return (
    <div className="space-y-3">
      {issues.map((issue) => (
        <DialogueIssueCard
          key={`${issue.original_quote}|${issue.diagnosis}`}
          issue={issue}
          editor={editor}
          onApplied={onApplied}
        />
      ))}
    </div>
  );
}
