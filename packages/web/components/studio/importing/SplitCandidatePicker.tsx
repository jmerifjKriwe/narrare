"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import type { ImportSplitCandidate } from "@/types";

/**
 * Inline candidate checklist for the split affordance (no dialog
 * dependency): the user selects which `###`+ subheadings become new chapter
 * boundaries, then applies. Ordinals are the chapter's capped candidate
 * ordinals — the original-space op input applySplit stores.
 */
interface SplitCandidatePickerProps {
  readonly candidates: readonly ImportSplitCandidate[];
  readonly onApply: (ordinals: number[]) => void;
  readonly onCancel: () => void;
}

export function SplitCandidatePicker({ candidates, onApply, onCancel }: SplitCandidatePickerProps) {
  const t = useTranslations("importing.ops");
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const toggle = (ordinal: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(ordinal)) next.delete(ordinal);
      else next.add(ordinal);
      return next;
    });
  };

  if (candidates.length === 0) {
    // Unreachable through the panel (the Split button is gated on
    // candidates.length > 0) — kept as the component's own empty state.
    return <p className="mt-2 text-xs text-muted-foreground">{t("noSplitPoints")}</p>;
  }

  return (
    <div
      className="mt-2 rounded-md border border-border bg-background p-3"
      data-testid="split-candidate-picker"
    >
      <p className="text-xs font-medium text-foreground">{t("splitPoints")}</p>
      <p className="mt-0.5 text-xs text-muted-foreground">{t("splitHint")}</p>
      <ul className="mt-2 max-h-40 overflow-y-auto">
        {candidates.map((candidate) => (
          <li key={candidate.ordinal} className="flex items-center gap-2 py-0.5">
            <input
              type="checkbox"
              id={`split-cand-${candidate.ordinal}`}
              checked={selected.has(candidate.ordinal)}
              onChange={() => toggle(candidate.ordinal)}
              className="h-4 w-4"
            />
            <label htmlFor={`split-cand-${candidate.ordinal}`} className="text-sm">
              {candidate.heading}
            </label>
          </li>
        ))}
      </ul>
      <div className="mt-2 flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md bg-secondary px-3 py-1.5 text-xs font-medium text-secondary-foreground hover:bg-accent transition-colors"
        >
          {t("cancel")}
        </button>
        <button
          type="button"
          data-testid="apply-split-btn"
          disabled={selected.size === 0}
          onClick={() => onApply([...selected].sort((a, b) => a - b))}
          className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {t("applySplit")}
        </button>
      </div>
    </div>
  );
}
