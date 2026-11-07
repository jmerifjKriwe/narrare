import { useState, type FormEvent } from "react";

import { client, type Chapter } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { queryClient, useNovelQuery } from "@shell/lib/query";
import { Button } from "@shell/ui/Button";
import { Dialog } from "@shell/ui/Dialog";
import { Field, Input } from "@shell/ui/field";
import { Notice } from "@shell/ui/Notice";

const DAY_MS = 86_400_000;

/** Whole days since an ISO stamp, floored at zero — a stamp in the future
 *  reads as today, never as a negative age. */
function daysSince(timestamp: string, now: number): number {
  return Math.max(0, Math.floor((now - Date.parse(timestamp)) / DAY_MS));
}

/** The catalog's call signature, InterchangeDialogs' own alias. */
type Translate = ReturnType<typeof useTranslation>;

/**
 * The chapter's export line (§5): the book's `last_exported_at` against
 * *this chapter's* `updated_at` — never exported, unchanged since, or
 * changed since. The comparison is scoped to the chapter's own content on
 * purpose: a reorder after the export changed the archive's order, not
 * this chapter's words, and that story belongs to the novel's line
 * (Task 12), not to this one.
 */
function chapterExportLine(chapter: Chapter, exportedAt: string | null, t: Translate): string {
  if (exportedAt === null) return t("chapters.exportNever");
  return Date.parse(chapter.updated_at) <= Date.parse(exportedAt)
    ? t("chapters.exportFresh", { count: daysSince(exportedAt, Date.now()) })
    : t("chapters.exportStale");
}

/** The chapter's own name for a sentence: its title, or the position the
 *  placeholder would give an untitled row. */
function chapterName(chapter: Chapter, t: Translate): string {
  return chapter.title || t("chapters.defaultTitle", { n: chapter.position + 1 });
}

/**
 * Rename a chapter in a dialog (an input inside a grid row would fight the
 * keyboard model the rail just chose). The write is the same one the
 * runhead's input would make — the title alone, through the endpoint's
 * dirty-field contract — so a body edit pending on this chapter is safe:
 * the next flush carries the body only and cannot undo the rename.
 *
 * The answer is the row as the server holds it (trimmed, touched): it
 * reaches the chapters cache before the invalidation's refetch, so the
 * rail cannot wear the old name past this moment. `onRenamed` hands the
 * server's title back, because the page's held draft — and with it the
 * runhead's input — must not keep the name the dialog just replaced.
 */
export function ChapterRenameDialog({
  chapter,
  open,
  onOpenChange,
  onRenamed,
}: {
  chapter: Chapter;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called with the server's title once the rename landed. */
  onRenamed?: (title: string) => void;
}) {
  const t = useTranslation();
  return (
    <Dialog title={t("chapters.renameTitle")} isOpen={open} onOpenChange={onOpenChange}>
      {(close) => <RenameForm chapter={chapter} close={close} onRenamed={onRenamed} />}
    </Dialog>
  );
}

/** The dialog's own state, mounted fresh on every open — the export form's
 *  pattern, so a previous open's input and refusal never leak into this
 *  one. */
function RenameForm({
  chapter,
  close,
  onRenamed,
}: {
  chapter: Chapter;
  close: () => void;
  onRenamed?: (title: string) => void;
}) {
  const t = useTranslation();
  const [title, setTitle] = useState(chapter.title);
  const [busy, setBusy] = useState(false);
  const [refusal, setRefusal] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setRefusal(false);
    try {
      // The title alone: the endpoint's `exclude_none` leaves the body
      // untouched, and the autosave's dirty-field contract means a body
      // pending flush never carries the title back over this write.
      const { data, response } = await client.PUT("/api/writing/chapters/{chapter_id}", {
        params: { path: { chapter_id: chapter.id } },
        body: { title },
      });
      if (!response.ok || !data) {
        setRefusal(true);
        return;
      }
      queryClient.setQueryData<Array<Chapter>>(["chapters", chapter.novel_id], (rows) =>
        rows?.map((row) => (row.id === chapter.id ? data : row)),
      );
      void queryClient.invalidateQueries({ queryKey: ["chapters", chapter.novel_id] });
      void queryClient.invalidateQueries({ queryKey: ["novels"] });
      onRenamed?.(data.title);
      close();
    } catch {
      setRefusal(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={(event) => void submit(event)} className="mt-4 flex flex-col gap-3">
      <Field label={t("chapters.renameLabel")}>
        {/* The same ceiling the runhead's input holds and the server
            checks: 200 characters, client-side. */}
        <Input
          value={title}
          maxLength={200}
          onChange={(event) => setTitle(event.target.value)}
        />
      </Field>
      {refusal ? (
        <Notice tone="danger" live="alert">
          {t("chapters.errorRename")}
        </Notice>
      ) : null}
      <div className="flex justify-end gap-3">
        <Button type="button" onClick={close}>
          {t("chapters.cancel")}
        </Button>
        <Button type="submit" variant="primary" disabled={busy}>
          {t("chapters.rename")}
        </Button>
      </div>
    </form>
  );
}

/**
 * Delete a chapter: the sentence names what dies, the export line under it
 * says what the archive would lose, and nothing is deleted on the first
 * click. The delete itself is the page's to orchestrate — retire the
 * pending document before the request flies, then open the chapter that
 * takes this one's place — so it arrives as `onDelete` and the dialog only
 * owns the asking: busy while it runs, the refusal named when it did not
 * land.
 */
export function ChapterDeleteDialog({
  novelId,
  chapter,
  open,
  onOpenChange,
  onDelete,
}: {
  novelId: string;
  chapter: Chapter;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Runs the orchestrated delete for the chapter this dialog names;
   *  resolves false when it did not land. */
  onDelete: (chapterId: string) => Promise<boolean>;
}) {
  const t = useTranslation();
  return (
    <Dialog title={t("chapters.deleteTitle")} isOpen={open} onOpenChange={onOpenChange}>
      {(close) => (
        <DeleteForm novelId={novelId} chapter={chapter} close={close} onDelete={onDelete} />
      )}
    </Dialog>
  );
}

function DeleteForm({
  novelId,
  chapter,
  close,
  onDelete,
}: {
  novelId: string;
  chapter: Chapter;
  close: () => void;
  onDelete: (chapterId: string) => Promise<boolean>;
}) {
  const t = useTranslation();
  // The export line reads the novel row through the same cache the
  // workbench reads — no ask of its own while it stands.
  const novelQuery = useNovelQuery(novelId);
  const [busy, setBusy] = useState(false);
  const [refusal, setRefusal] = useState(false);
  const name = chapterName(chapter, t);
  const line = chapterExportLine(chapter, novelQuery.data?.last_exported_at ?? null, t);

  async function confirm() {
    setBusy(true);
    setRefusal(false);
    // The page's orchestration never throws past this guard; the catch is
    // for honesty, not expectation.
    const landed = await onDelete(chapter.id).catch(() => false);
    setBusy(false);
    if (landed) {
      close();
      return;
    }
    setRefusal(true);
  }

  return (
    <div className="mt-4 flex flex-col gap-3">
      <p className="text-body text-muted">{t("chapters.deleteBody", { title: name })}</p>
      <p className="text-meta text-muted">{line}</p>
      {refusal ? (
        <Notice tone="danger" live="alert">
          {t("chapters.errorDelete")}
        </Notice>
      ) : null}
      <div className="mt-2 flex justify-end gap-3">
        <Button onClick={close}>{t("chapters.cancel")}</Button>
        <Button variant="primary" disabled={busy} onClick={() => void confirm()}>
          {t("chapters.delete")}
        </Button>
      </div>
    </div>
  );
}
