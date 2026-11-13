import { useState, type FormEvent } from "react";

import { Button } from "@shell/ui/Button";
import { type Novel, type NovelCreate } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { dirtyFields } from "@shell/lib/dirty";
import { exportAge } from "@shell/lib/exportAge";
import {
  useCreateNovel,
  useDeleteNovel,
  useEntitiesQuery,
  useNovelQuery,
  useUpdateNovel,
  type NovelChanges,
} from "@shell/lib/query";
import { Dialog } from "@shell/ui/Dialog";
import { Field, Input, Textarea } from "@shell/ui/field";
import { Icon } from "@shell/ui/icons";
import { Notice } from "@shell/ui/Notice";

import { ExportNovelDialog } from "../InterchangeDialogs";

/**
 * The shelf's three dialogs, moved beside the shelf they serve: the
 * new-book form, the book's details and the delete warning. Their
 * contracts are the ones the writing capability shipped — the new-book
 * form's refusal-by-name, the details form's save-only-what-changed
 * (the PATCH's `model_fields_set` contract mirrored client-side), the
 * delete's naming of what dies with the export line one press away.
 */

/**
 * The new-book dialog's form, with its own state: the fields, the empty
 * title's refusal and the create's failure all live and die with one
 * mounting — the dialog mounts its content fresh on every open, so nothing
 * here can outlive the dialog it belongs to. The empty Titel is refused by
 * name, not by silence: the failed submit marks the field, and the mark
 * lifts as soon as the field answers it. Derived, not stored, so typing a
 * title can never leave a stale refusal.
 */
export function NewBookForm({ close }: { close: () => void }) {
  const t = useTranslation();
  const createNovel = useCreateNovel();
  const [title, setTitle] = useState("");
  const [genre, setGenre] = useState("");
  const [blurb, setBlurb] = useState("");
  const [createFailed, setCreateFailed] = useState(false);
  const [triedEmptyTitle, setTriedEmptyTitle] = useState(false);
  const titleInvalid = triedEmptyTitle && title.trim() === "";

  /** Create a book from trimmed fields; close on success and retain the form on failure. */
  async function create(event: React.FormEvent) {
    event.preventDefault();
    if (title.trim() === "") {
      setTriedEmptyTitle(true);
      return;
    }
    setCreateFailed(false);
    // Only fields the user filled reach the row: an empty genre is no genre,
    // not a genre called "".
    const input: NovelCreate = { title: title.trim() };
    if (genre.trim() !== "") input.genre = genre.trim();
    if (blurb.trim() !== "") input.blurb = blurb.trim();
    try {
      // The list refreshes through the ["novels"] invalidation, not through
      // a reload here: the mutation owns that side of the contract.
      await createNovel.mutateAsync(input);
    } catch {
      // The dialog stays open: the typed values are the user's work, and
      // the failure is this create's own — named inside the dialog, where
      // the retry is one press away, not on a page behind it.
      setCreateFailed(true);
      return;
    }
    close();
  }

  return (
    <form onSubmit={(event) => void create(event)} className="mt-4 flex flex-col gap-3">
      <Field
        label={t("novels.titleLabel")}
        error={titleInvalid ? t("novels.titleRequired") : undefined}
      >
        <Input value={title} onChange={(event) => setTitle(event.target.value)} />
      </Field>
      <Field label={t("novels.genre")}>
        <Input value={genre} onChange={(event) => setGenre(event.target.value)} />
      </Field>
      <Field label={t("novels.blurb")}>
        <Textarea
          value={blurb}
          onChange={(event) => setBlurb(event.target.value)}
          rows={3}
        />
      </Field>
      {createFailed ? (
        <Notice tone="danger" live="alert">
          {t("novels.errorCreate")}
        </Notice>
      ) : null}
      <Button type="submit" variant="primary" className="self-start">
        {t("novels.create")}
      </Button>
    </form>
  );
}

/** The language field's own contract, the server's shape seen from the
 *  typing side: the server folds the primary subtag's case (`DE` is `de`),
 *  so both cases pass here and the server owns the folding. */
const LANGUAGE_CODE = /^[a-zA-Z]{2}(-[A-Za-z]{2,})?$/;

/**
 * The book's five metadata fields (D5), in the new-book form's own
 * field/refusal style: the empty Titel is refused by name, the language is
 * validated text — `de`, `en-GB`, anything BCP-47-ish an import can carry —
 * refused on its field before the wire and again by the server's 422 naming
 * it. Controlled by the card's menu, mounted fresh on every open: the
 * fields, the refusals and the failure all live and die with one opening.
 *
 * The save sends only the fields the user changed — the client's mirror of
 * the endpoint's `model_fields_set` contract, so a correction never
 * rewrites the fields nobody touched. An unchanged form closes without a
 * request: nothing to ask, nothing to write.
 */
export function NovelDetailsDialog({
  novel,
  open,
  onOpenChange,
}: {
  novel: Novel;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const t = useTranslation();
  return (
    <Dialog title={t("novels.detailsTitle")} isOpen={open} onOpenChange={onOpenChange}>
      {(close) => <DetailsForm novel={novel} close={close} />}
    </Dialog>
  );
}

function DetailsForm({ novel, close }: { novel: Novel; close: () => void }) {
  const t = useTranslation();
  const updateNovel = useUpdateNovel();
  const [title, setTitle] = useState(novel.title);
  const [author, setAuthor] = useState(novel.author ?? "");
  const [genre, setGenre] = useState(novel.genre ?? "");
  const [language, setLanguage] = useState(novel.language ?? "");
  const [blurb, setBlurb] = useState(novel.blurb ?? "");
  const [triedEmptyTitle, setTriedEmptyTitle] = useState(false);
  const [triedBadLanguage, setTriedBadLanguage] = useState(false);
  // The server's own refusal naming the language: shown whatever the
  // pattern says — the wire refused this value, and the field is where the
  // refusal is answered. Typing lifts it, like the derived marks.
  const [languageRefused, setLanguageRefused] = useState(false);
  const [updateFailed, setUpdateFailed] = useState(false);
  const [deletedElsewhere, setDeletedElsewhere] = useState(false);
  const [busy, setBusy] = useState(false);
  // Derived, not stored, so typing lifts the mark: a refusal the field can
  // answer never outlives the answer. The language's rule is the guard's
  // own — a non-empty value that is not BCP-47-ish — so the mark and the
  // refusal can never disagree about what a cleared field is: a clear.
  const titleInvalid = triedEmptyTitle && title.trim() === "";
  const badLanguage = language.trim() !== "" && !LANGUAGE_CODE.test(language.trim());
  const languageInvalid = triedBadLanguage && badLanguage;

  /** Save the changed fields; close on success and retain the form on
   *  failure — the typed values are the user's work. */
  async function save(event: FormEvent) {
    event.preventDefault();
    if (title.trim() === "") {
      setTriedEmptyTitle(true);
      return;
    }
    // Empty is the cleared state, not a bad code: only a non-empty value
    // that is not BCP-47-ish is refused — the same predicate the field's
    // mark reads, so the guard and the mark cannot disagree.
    if (badLanguage) {
      setTriedBadLanguage(true);
      return;
    }
    setUpdateFailed(false);
    // Only what differs from the row the form loaded: the candidate is the
    // value the wire would carry (trimmed, empty as the cleared `null`),
    // compared against the stored field — a field typed and reverted is no
    // change, and an untouched form is no request at all.
    const written: NovelChanges = {
      title: title.trim(),
      author: author.trim() === "" ? null : author.trim(),
      genre: genre.trim() === "" ? null : genre.trim(),
      language: language.trim() === "" ? null : language.trim(),
      blurb: blurb.trim() === "" ? null : blurb.trim(),
    };
    // Normalize the stored values through the same trim-to-null rule the
    // candidate uses, so a hand-edited empty string compares equal to a
    // cleared (null) field instead of marking the row dirty (#698).
    const dirty = dirtyFields(written, {
      title: novel.title,
      author: (novel.author ?? "").trim() || null,
      genre: (novel.genre ?? "").trim() || null,
      language: (novel.language ?? "").trim() || null,
      blurb: (novel.blurb ?? "").trim() || null,
    });
    if (dirty.length === 0) {
      close();
      return;
    }
    const changes = Object.fromEntries(
      dirty.map((field) => [field, written[field]]),
    ) as NovelChanges;
    setBusy(true);
    try {
      // The list and the row refresh through the ["novels"] invalidation,
      // not through a reload here: the mutation owns that side.
      await updateNovel.mutateAsync({ novelId: novel.id, changes });
    } catch (error) {
      // The one refusal the form can answer on its field: the server named
      // the language. Every other refusal — the service is not answering,
      // a row that vanished under the dialog — is the dialog's own
      // sentence, named where the retry is one press away.
      if ((error as { detail?: unknown }).detail === "invalid language") {
        setLanguageRefused(true);
        return;
      }
      if ((error as { status?: number }).status === 404) {
        setDeletedElsewhere(true);
        return;
      }
      setUpdateFailed(true);
      return;
    } finally {
      setBusy(false);
    }
    close();
  }

  return (
    // noValidate: the named refusals are the catalog's voice in every
    // browser — the pattern the language field carries is the rule's
    // semantics, not a second message beside the first.
    <form onSubmit={(event) => void save(event)} noValidate className="mt-4 flex flex-col gap-3">
      <Field
        label={t("novels.titleLabel")}
        error={titleInvalid ? t("novels.titleRequired") : undefined}
      >
        <Input
          value={title}
          maxLength={200}
          onChange={(event) => setTitle(event.target.value)}
        />
      </Field>
      <Field label={t("novels.author")}>
        <Input
          value={author}
          maxLength={200}
          onChange={(event) => setAuthor(event.target.value)}
        />
      </Field>
      <Field label={t("novels.genre")}>
        <Input
          value={genre}
          maxLength={80}
          onChange={(event) => setGenre(event.target.value)}
        />
      </Field>
      <Field
        label={t("novels.language")}
        error={
          languageInvalid || languageRefused ? t("novels.languageInvalid") : undefined
        }
      >
        <Input
          value={language}
          maxLength={16}
          pattern="[a-zA-Z]{2}(-[A-Za-z]{2,})?"
          onChange={(event) => {
            setLanguageRefused(false);
            setLanguage(event.target.value);
          }}
        />
      </Field>
      <Field label={t("novels.blurb")}>
        <Textarea
          value={blurb}
          onChange={(event) => setBlurb(event.target.value)}
          rows={3}
        />
      </Field>
      {deletedElsewhere ? (
        <Notice tone="danger" live="alert">
          {t("novels.deleteElsewhere")}
        </Notice>
      ) : null}
      {updateFailed ? (
        <Notice tone="danger" live="alert">
          {t("novels.errorUpdate")}
        </Notice>
      ) : null}
      <Button type="submit" variant="primary" className="self-start" disabled={busy}>
        {t("novels.save")}
      </Button>
    </form>
  );
}

/**
 * Delete a book: the sentence names what dies — chapters from the row the
 * card already holds, knowledge entries from the list the dialog opens
 * with (no shelf read pays for a count only this warning needs) — says the
 * documents stay, and carries the export line from `exportAge` over the
 * row the dialog reads through Query. "Export now" sits beside the line
 * (the path mode's dialog, stacked over this one): a landed export
 * invalidates the row, and the line recomputes from the refetch — the
 * warning and its way out in one place. Nothing is deleted on the first
 * click; the confirm is final and the refusal is named where it happened.
 */
export function NovelDeleteDialog({
  novel,
  open,
  onOpenChange,
}: {
  novel: Novel;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const t = useTranslation();
  return (
    <Dialog title={t("novels.deleteTitle")} isOpen={open} onOpenChange={onOpenChange}>
      {(close) => <DeleteForm novel={novel} close={close} />}
    </Dialog>
  );
}

function DeleteForm({ novel, close }: { novel: Novel; close: () => void }) {
  const t = useTranslation();
  const deleteNovel = useDeleteNovel();
  // The row through the cache, not the card's prop: the export the dialog
  // itself offers invalidates the row on success, and the line recomputes
  // from the answer — the prop is the fallback while the ask stands.
  const novelQuery = useNovelQuery(novel.id);
  const row = novelQuery.data ?? novel;
  // The knowledge count opens with the dialog: the content mounts only
  // while it stands, so the shelf never pays for a number only this
  // warning reads — and the chapters never wait behind it: that count is
  // the row's own fact, already on the card that opened this dialog.
  const entities = useEntitiesQuery(novel.id);
  const [exportOpen, setExportOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [refusal, setRefusal] = useState(false);
  const age = exportAge(row.last_exported_at, row.updated_at, new Date());
  const line =
    age.kind === "never"
      ? t("novels.exportNever")
      : age.kind === "fresh"
        ? t("novels.exportFresh")
        : t("novels.exportStale", { count: age.days });

  /** Confirm the delete: the 204 closes, a refusal stays and is named. */
  async function confirm() {
    setBusy(true);
    setRefusal(false);
    try {
      await deleteNovel.mutateAsync(novel.id);
    } catch {
      setRefusal(true);
      return;
    } finally {
      setBusy(false);
    }
    close();
  }

  return (
    <div className="mt-4 flex flex-col gap-3">
      <p className="text-body text-muted">
        {t("novels.deleteBody", { title: row.title })}
      </p>
      {/* What dies, said as soon as it is known: the chapters are the
          row's own fact and never wait behind the entities ask — the
          entity half joins when its read lands, and is absent (never a
          guessed zero) until then. */}
      <p className="text-body text-muted">
        {t("novels.deleteChapters", { chapters: row.chapter_count })}
        {entities.data !== undefined ? (
          <>
            {" "}
            <span>{t("novels.deleteEntities", { entities: entities.data.length })}</span>
          </>
        ) : entities.isError ? (
          <>
            {" "}
            <span>{t("novels.deleteEntitiesUnavailable")}</span>
          </>
        ) : null}
      </p>
      <p className="text-body text-muted">{t("novels.deleteDocuments")}</p>
      <p className="text-meta text-muted">{line}</p>
      <Button
        variant="secondary"
        icon={<Icon name="export" />}
        className="self-start"
        onClick={() => setExportOpen(true)}
      >
        {t("novels.exportNow")}
      </Button>
      {refusal ? (
        <Notice tone="danger" live="alert">
          {t("novels.errorDelete")}
        </Notice>
      ) : null}
      <div className="mt-2 flex justify-end gap-3">
        <Button disabled={busy} onClick={close}>{t("novels.cancel")}</Button>
        <Button variant="primary" disabled={busy} onClick={() => void confirm()}>
          {t("novels.delete")}
        </Button>
      </div>
      <ExportNovelDialog novel={row} isOpen={exportOpen} onOpenChange={setExportOpen} />
    </div>
  );
}
