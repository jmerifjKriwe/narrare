"use client";

/**
 * NoteScopeSelect — the grouped novel/series scope filter select used by
 * NoteFilterBar (NOTES-001 §7: "novel/series filter — only if linked notes
 * exist").
 *
 * Owns the WHEN-not-WHERE policy's rendering side: one grouped select
 * (All / novels / series) fed by `novels` and `series` (parents map
 * useNovels()/useSeriesList() results down to {id, title}). WHETHER it is
 * rendered at all is the parent's decision — NoteFilterBar mounts it only
 * while `hasLinks` is true AND at least one list is non-empty.
 *
 * The selection flows up as a typed `NoteScopeFilter` object ({kind, id} —
 * not a merged string, so the parent maps it type-safely onto
 * NoteListParams.novel_id / series_id). The DOM value encoding
 * ("novel:<id>" / "series:<id>" / "") is a private detail of this module
 * (UUIDs contain no colons). Controlled-select safety: a scope whose target
 * vanished from both lists still gets a fallback option (raw id) so the
 * select never renders blank while the filter is factually active —
 * clearing a stale scope is the parent's responsibility.
 */

import { useTranslations } from "next-intl";

/** Novel/series option for the grouped scope select. */
export interface ScopeOption {
  readonly id: string;
  readonly title: string;
}

/**
 * Active scope filter. `kind` + `id` instead of one merged string so the
 * parent's mapping onto NoteListParams stays type-safe.
 */
export interface NoteScopeFilter {
  readonly kind: "novel" | "series";
  readonly id: string;
}

export interface NoteScopeSelectProps {
  /** Active scope filter; null = "All" (no scope restriction). */
  readonly value: NoteScopeFilter | null;
  readonly onChange: (scope: NoteScopeFilter | null) => void;
  readonly novels: readonly ScopeOption[];
  readonly series: readonly ScopeOption[];
}

/** Scope select value encoding: "" | "novel:<id>" | "series:<id>". */
function encodeScopeValue(scope: NoteScopeFilter | null): string {
  return scope ? `${scope.kind}:${scope.id}` : "";
}

/** Inverse of encodeScopeValue; unknown shapes decode to null. */
function decodeScopeValue(value: string): NoteScopeFilter | null {
  if (!value) return null;
  const separator = value.indexOf(":");
  const kind = value.slice(0, separator);
  const id = value.slice(separator + 1);
  return (kind === "novel" || kind === "series") && id ? { kind, id } : null;
}

export function NoteScopeSelect({ value, onChange, novels, series }: NoteScopeSelectProps) {
  const t = useTranslations("notes");

  // A scope whose target vanished from both lists still needs a matching
  // option, or the select renders blank while the filter is active.
  const scopeKnown =
    value !== null &&
    ((value.kind === "novel" && novels.some((n) => n.id === value.id)) ||
      (value.kind === "series" && series.some((s) => s.id === value.id)));

  return (
    <label className="flex items-center gap-1.5 text-sm font-normal text-muted-foreground">
      <span className="sr-only sm:not-sr-only">{t("list.scopeFilterLabel")}</span>
      <select
        value={encodeScopeValue(value)}
        data-testid="note-scope-filter"
        aria-label={t("list.scopeFilterLabel")}
        className="cursor-pointer rounded-md border border-border bg-background px-2 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        onChange={(event) => onChange(decodeScopeValue(event.target.value))}
      >
        <option value="">{t("list.allScopes")}</option>
        {novels.length > 0 && (
          <optgroup label={t("list.scopeNovelsGroup")}>
            {novels.map((novel) => (
              <option key={novel.id} value={`novel:${novel.id}`}>
                {novel.title}
              </option>
            ))}
          </optgroup>
        )}
        {series.length > 0 && (
          <optgroup label={t("list.scopeSeriesGroup")}>
            {series.map((item) => (
              <option key={item.id} value={`series:${item.id}`}>
                {item.title}
              </option>
            ))}
          </optgroup>
        )}
        {value && !scopeKnown && <option value={encodeScopeValue(value)}>{value.id}</option>}
      </select>
    </label>
  );
}
