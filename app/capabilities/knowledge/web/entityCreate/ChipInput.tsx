/**
 * The create dialog's chip input (moved from crudDialogs, W9 Task 11): the
 * screen's «Mit Enter hinzufügen». Enter commits the draft, leaving the field
 * commits it too, and the save flushes whatever draft is still standing — a
 * label typed without Enter is never discarded. The 200-character cap mirrors
 * the name input.
 */
import { useId } from "react";

import { useTranslation } from "@shell/lib/i18n";
import { FOCUS } from "@shell/ui/card";
import { Icon } from "@shell/ui/icons";

import { NAME_MAX } from "../crudDialogs";
import { SuggestedMark } from "./SuggestedMark";

/** The chip list after a draft: trimmed, folded into an existing chip
 *  case-insensitively, or appended when it is new. The API dedupes too, so
 *  the form never sends a doubled label. */
export function withChip(values: readonly string[], draft: string): string[] {
  const value = draft.trim();
  if (value === "") return [...values];
  if (values.some((existing) => existing.toLowerCase() === value.toLowerCase())) return [...values];
  return [...values, value];
}

export function ChipInput({
  testId,
  label,
  hint,
  placeholder,
  values,
  draft,
  onDraftChange,
  onChange,
  suggestedValues,
}: {
  testId: string;
  label: string;
  hint: string;
  placeholder: string;
  values: readonly string[];
  draft: string;
  onDraftChange: (draft: string) => void;
  onChange: (values: string[]) => void;
  /** The values the interview's model proposed; each carries its mark. */
  suggestedValues?: readonly string[];
}) {
  const id = useId();
  const t = useTranslation();
  function commit() {
    const value = draft.trim();
    onDraftChange("");
    if (value === "") return;
    onChange(withChip(values, value));
  }
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <label htmlFor={id} className="block text-meta font-medium text-foreground">
          {label}
        </label>
        <span className="text-[11px] text-muted">{hint}</span>
      </div>
      <div className="flex min-h-8 flex-wrap items-center gap-1 rounded border border-border bg-surface-container-low px-2.5 py-1.5">
        {values.map((value) => (
          <span
            key={value}
            className="inline-flex items-center gap-1 rounded bg-surface-container-high px-2 py-0.5 text-[12px] font-medium text-foreground"
          >
            {value}
            {suggestedValues?.includes(value) === true && <SuggestedMark />}
            <button
              type="button"
              aria-label={`${t("knowledge.create.removeChip")}: ${value}`}
              onClick={() => onChange(values.filter((existing) => existing !== value))}
              className={`flex items-center text-muted transition-colors hover:text-foreground ${FOCUS}`}
            >
              <Icon name="cross" size={10} />
            </button>
          </span>
        ))}
        <input
          id={id}
          data-testid={testId}
          type="text"
          value={draft}
          maxLength={NAME_MAX}
          placeholder={placeholder}
          onChange={(event) => onDraftChange(event.target.value)}
          onBlur={commit}
          onKeyDown={(event) => {
            if (event.key !== "Enter") return;
            event.preventDefault();
            commit();
          }}
          className="min-w-[8rem] flex-1 bg-transparent text-body text-foreground outline-none placeholder:text-muted"
        />
      </div>
    </div>
  );
}
