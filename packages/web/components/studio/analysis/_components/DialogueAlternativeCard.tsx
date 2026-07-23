"use client";

import type { Editor } from "@tiptap/react";
/**
 * DialogueAlternativeCard — one proposed rewrite for a diagnosed issue.
 *
 * ADR-069 Decision 9: alternatives render as STACKED before/after blocks —
 * a red-tinted "original" and a green-tinted "rewrite" — and Accept applies
 * the rewrite by a FULL-STRING find-and-replace in the chapter (no
 * char-level diff library).
 *
 * Apply mechanism (the contract from the plan's `handleApply` skeleton, with
 * the real transaction filled in per the plan's implementation note): a
 * ProseMirror text-node scan locates `originalQuote` in the document and
 * replaces just that range via `tr.insertText(rewrite, from, to)`. If the
 * quote is not found (e.g. the doc has changed since analysis), Accept is a
 * graceful no-op (RULE-11) — it neither corrupts the document nor signals
 * success. `onApplied` fires only when a replacement actually landed.
 *
 * Frontend-design: the before/after blocks are the flagship AI-assist visual —
 * a cohesive red/green treatment with a left accent rail and an uppercase
 * tracking-wide label, kept restrained (5–20% tint fills, 20% borders) so the
 * content reads first.
 *
 * @module DialogueAlternativeCard
 */
import { Check } from "lucide-react";
import { useTranslations } from "next-intl";
import type { DialogueAlternative } from "@/types";

interface DialogueAlternativeCardProps {
  alternative: DialogueAlternative;
  originalQuote: string;
  editor: Editor;
  onApplied: () => void;
}

export function DialogueAlternativeCard({
  alternative,
  originalQuote,
  editor,
  onApplied,
}: DialogueAlternativeCardProps) {
  const t = useTranslations();

  /**
   * Apply the rewrite: find `originalQuote` in the document text and replace
   * that exact range with the rewrite. Returns without side-effects if the
   * quote is absent (graceful no-op, RULE-11).
   */
  const handleApply = () => {
    let applied = false;
    editor
      .chain()
      .focus()
      .command(({ tr, state }) => {
        state.doc.descendants((node, pos) => {
          if (applied) return false;
          if (!node.isText) return true;
          const text = node.text;
          if (!text) return true;
          const idx = text.indexOf(originalQuote);
          if (idx === -1) return true;
          tr.insertText(alternative.rewrite, pos + idx, pos + idx + originalQuote.length);
          applied = true;
          return false;
        });
        // Returning false when nothing matched keeps TipTap from recording an
        // empty transaction.
        return applied;
      })
      .run();
    if (applied) onApplied();
  };

  return (
    <div className="mt-3 space-y-2 border-l-2 border-border pl-3">
      {/* Before — the flagged original (red-tint). */}
      <div className="rounded-md bg-red-500/5 border border-red-500/20 p-2">
        <p className="text-[0.65rem] font-semibold uppercase tracking-wide text-red-600 dark:text-red-400">
          {t("dialogueCoach.alternatives.original")}
        </p>
        <p className="text-sm mt-0.5">{originalQuote}</p>
      </div>
      {/* After — the proposed rewrite (green-tint). */}
      <div className="rounded-md bg-emerald-500/5 border border-emerald-500/20 p-2">
        <p className="text-[0.65rem] font-semibold uppercase tracking-wide text-emerald-600 dark:text-emerald-400">
          {t("dialogueCoach.alternatives.rewrite")}
        </p>
        <p className="text-sm mt-0.5">{alternative.rewrite}</p>
        {alternative.explanation && (
          <p className="text-xs text-muted-foreground mt-1">{alternative.explanation}</p>
        )}
      </div>
      <button
        type="button"
        onClick={handleApply}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-primary text-primary-foreground hover:opacity-90 transition-opacity focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1"
      >
        <Check className="w-3.5 h-3.5" aria-hidden="true" />
        {t("dialogueCoach.alternatives.apply")}
      </button>
    </div>
  );
}
