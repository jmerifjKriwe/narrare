"use client";

/**
 * NoteEditorLinks — metadata footer of the editor (NOTES-001 §7): tag entry
 * (TagInput, T22) and the optional novel/series link selects.
 *
 * Owns the two dropdown list queries (useNovels / useSeriesList) — data
 * lives with its only consumer. The link pair is controlled as ONE draft
 * value so the scope invariant ("a note links to a novel OR a series,
 * never both") is enforced in a single place: picking one side clears the
 * other.
 */

import { useTranslations } from "next-intl";
import { useNovels } from "@/lib/hooks/useNovels";
import { useSeriesList } from "@/lib/hooks/useSeries";
import { TagInput } from "./TagInput";

/** Controlled draft of the note's scope links ("" = not linked). */
export interface NoteLinkDraft {
  readonly novelId: string;
  readonly seriesId: string;
}

export interface NoteEditorLinksProps {
  readonly links: NoteLinkDraft;
  readonly onLinksChange: (next: NoteLinkDraft) => void;
  readonly tags: readonly string[];
  /**
   * MUST be echoed into `tags` synchronously — state set in the same event
   * handler (binding T22 review constraint: TagInput's semi-controlled
   * mirror is unsafe with async/debounced parents).
   */
  readonly onTagsChange: (next: string[]) => void;
  readonly availableTags: readonly string[];
}

const SELECT_CLASS =
  "min-w-0 flex-1 rounded-md border border-border bg-background px-2 py-1.5 text-sm text-foreground transition-colors hover:border-muted-foreground/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

export function NoteEditorLinks({
  links,
  onLinksChange,
  tags,
  onTagsChange,
  availableTags,
}: NoteEditorLinksProps) {
  const t = useTranslations("notes");
  const { data: novels } = useNovels();
  const { data: seriesList } = useSeriesList();

  return (
    <div className="space-y-2 border-t border-border p-3">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
        {t("editor.tagsLabel")}
      </p>
      <TagInput value={tags} onChange={onTagsChange} suggestions={availableTags} />

      <p className="pt-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
        {t("editor.linkLabel")}
      </p>
      <div className="flex gap-2">
        <select
          value={links.novelId}
          data-testid="note-novel-link"
          aria-label={t("editor.novelLink")}
          className={SELECT_CLASS}
          onChange={(event) =>
            onLinksChange({
              novelId: event.target.value,
              // Scope invariant: linking a novel clears the series link.
              seriesId: event.target.value ? "" : links.seriesId,
            })
          }
        >
          <option value="">{t("editor.noLink")}</option>
          {(novels ?? []).map((novel) => (
            <option key={novel.id} value={novel.id}>
              {novel.title}
            </option>
          ))}
        </select>
        <select
          value={links.seriesId}
          data-testid="note-series-link"
          aria-label={t("editor.seriesLink")}
          className={SELECT_CLASS}
          onChange={(event) =>
            onLinksChange({
              seriesId: event.target.value,
              // Scope invariant: linking a series clears the novel link.
              novelId: event.target.value ? "" : links.novelId,
            })
          }
        >
          <option value="">{t("editor.noLink")}</option>
          {(seriesList ?? []).map((series) => (
            <option key={series.id} value={series.id}>
              {series.title}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
