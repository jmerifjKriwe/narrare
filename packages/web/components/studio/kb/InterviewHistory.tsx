"use client";

/**
 * InterviewHistory — scrollable, searchable timeline of interview Q&A pairs.
 *
 * Presentation only (RULE-06): receives the recorded entries and the session
 * fields (for label resolution), manages local search state, and renders the
 * filtered timeline using the SearchInput primitive.
 *
 * Extracted from KBInterviewView for RULE-04 compliance.
 */

import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";
import { SearchInput } from "@/components/ui/search-input";
import type { KBCreationField } from "@/lib/api/kb-sessions";
import type { InterviewQAEntry } from "@/lib/hooks/use-interview-history";

interface InterviewHistoryProps {
  /** Recorded Q&A pairs from the interview. */
  readonly entries: readonly InterviewQAEntry[];
  /** Session fields — used to resolve field keys to human labels for badges. */
  readonly fields: readonly KBCreationField[];
}

export function InterviewHistory({ entries, fields }: InterviewHistoryProps) {
  const t = useTranslations("studio");
  const [search, setSearch] = useState("");

  const labelFor = (key: string): string => fields.find((f) => f.field_key === key)?.label ?? key;

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return entries;
    return entries.filter(
      (entry) =>
        entry.question.toLowerCase().includes(term) || entry.answer.toLowerCase().includes(term),
    );
  }, [entries, search]);

  return (
    <div className="space-y-3 text-left">
      <SearchInput
        label={t("kb.interviewHistory")}
        placeholder={t("kb.interviewHistorySearch")}
        value={search}
        onValueChange={setSearch}
        onClear={() => setSearch("")}
        clearLabel={t("kb.clearSearch")}
        visibleLabel={false}
      />

      {filtered.length === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-6">
          {t("kb.interviewHistoryEmpty")}
        </p>
      ) : (
        <ol className="space-y-3 max-h-96 overflow-y-auto">
          {filtered.map((entry) => (
            <li
              key={`${entry.fieldKey}-${entry.question}`}
              className="rounded-lg border border-border bg-card p-3 space-y-1"
            >
              <p className="text-xs text-muted-foreground">{entry.question}</p>
              <p className="text-sm text-foreground whitespace-pre-wrap">{entry.answer}</p>
              {entry.fieldKey && (
                <span className="inline-block mt-1 px-2 py-0.5 text-[10px] rounded-full bg-muted text-muted-foreground">
                  {labelFor(entry.fieldKey)}
                </span>
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
