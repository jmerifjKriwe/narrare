import { useId, useRef, useState } from "react";
import type { FormEvent } from "react";

import type { Novel } from "@shell/lib/api/client";
import { announce } from "@shell/lib/announce";
import { useTranslation } from "@shell/lib/i18n";
import { queryClient } from "@shell/lib/query";
import { Dialog } from "@shell/ui/Dialog";
import { TextField } from "@shell/ui/TextField";

import {
  detailOf,
  downloadBlob,
  exportNovel,
  importArchive,
  proposeExportPath,
  type ExportMode,
  type ExportReceipt,
  type ImportReport,
  type InterchangeFailure,
} from "./interchange";

const PRIMARY_BUTTON =
  "self-start rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50";
const QUIET_BUTTON =
  "self-start rounded-md border border-border px-3 py-2 text-sm font-medium hover:bg-panel focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

/** One labelled radio row: native input, native keyboard reach. */
function RadioRow({
  label,
  name,
  checked,
  onPick,
}: {
  label: string;
  name: string;
  checked: boolean;
  onPick: () => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <input type="radio" name={name} checked={checked} onChange={onPick} />
      {label}
    </label>
  );
}

/** A named refusal inside the dialog, where the retry is one press away. */
function FailureAlert({ message }: { message: string }) {
  return <p role="alert" className="text-sm text-danger">{message}</p>;
}

/**
 * Export one shelf novel: into a folder on disk (the receipt shows where
 * and how much) or as a ZIP download (the archive goes to the browser,
 * the dialog closes — the download itself is the report). The path input
 * is prefilled with a timestamped proposal so the common export lands on
 * a fresh folder and the refusal on non-empty targets stays the exception
 * it is meant to be.
 */
export function ExportNovelDialog({ novel }: { novel: Novel }) {
  const t = useTranslation();
  return (
    <Dialog
      title={t("shelf.exportTitle", { title: novel.title })}
      triggerLabel={t("shelf.export")}
      // Every row shows the same word; the accessible name carries this
      // novel, so a screen reader's button list stays unambiguous.
      triggerAriaLabel={t("shelf.exportTitle", { title: novel.title })}
    >
      {(close) => <ExportForm novel={novel} close={close} />}
    </Dialog>
  );
}

/** Mounted fresh on every open: the proposal, mode and receipt are this
 *  dialog's own, never a previous one's leftovers. */
function ExportForm({ novel, close }: { novel: Novel; close: () => void }) {
  const t = useTranslation();
  const receiptId = useId();
  const [mode, setMode] = useState<ExportMode>("path");
  // The proposal is computed once at open: the user's edit is the answer
  // from there, not a suggestion the dialog keeps overwriting.
  const [path, setPath] = useState(() => proposeExportPath(novel.title));
  const [receipt, setReceipt] = useState<ExportReceipt | null>(null);
  const [refusal, setRefusal] = useState<string | null>(null);
  const [triedEmptyPath, setTriedEmptyPath] = useState(false);
  const [busy, setBusy] = useState(false);
  // Derived, not stored: typing lifts the mark, like the shelf's own form.
  const pathInvalid = triedEmptyPath && path.trim() === "";

  async function submit(event: FormEvent) {
    event.preventDefault();
    setRefusal(null);
    if (mode === "path" && path.trim() === "") {
      setTriedEmptyPath(true);
      return;
    }
    setBusy(true);
    try {
      const result = await exportNovel(
        novel.id,
        mode,
        mode === "path" ? path.trim() : undefined,
        `${proposeExportPath(novel.title)}.zip`,
      );
      if ("blob" in result) {
        // The ZIP's report is the download itself; nothing to show, much
        // to claim — the announcement says the archive left, and the
        // dialog steps out of its way.
        downloadBlob(result.blob, result.filename);
        announce(t("shelf.export.zipDone"));
        close();
        return;
      }
      // The receipt replaces the form on screen; a non-visual reader gets
      // the same answer in one line, because the form it was typing into
      // just went away.
      setReceipt(result);
      announce(
        [
          t("shelf.export.doneHeading"),
          t("shelf.export.donePath", { path: result.path }),
          t("shelf.export.doneChapters", { count: result.chapters }),
          t("shelf.export.doneEntities", { count: result.entities }),
        ].join(" "),
      );
    } catch (error) {
      const status = (error as InterchangeFailure).status;
      const detail = detailOf(error) as { code?: string; path?: string } | undefined;
      if (detail?.code === "target_not_empty") {
        setRefusal(t("shelf.export.targetNotEmpty", { path: detail.path ?? "" }));
      } else if (status >= 400 && status < 500) {
        // The server answered and named no fix: a typo path, a missing
        // folder — the outage guess would blame the wrong thing.
        setRefusal(t("shelf.export.refused"));
      } else {
        setRefusal(t("shelf.export.error"));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-4 flex flex-col gap-3">
      {receipt ? (
        <>
          <div aria-labelledby={receiptId} className="flex flex-col gap-1 text-sm">
            <h3 id={receiptId} className="font-medium">
              {t("shelf.export.doneHeading")}
            </h3>
            <p>{t("shelf.export.donePath", { path: receipt.path })}</p>
            <p>{t("shelf.export.doneChapters", { count: receipt.chapters })}</p>
            <p>{t("shelf.export.doneEntities", { count: receipt.entities })}</p>
          </div>
          <button type="button" onClick={close} className={QUIET_BUTTON}>
            {t("shelf.export.close")}
          </button>
        </>
      ) : (
        <form onSubmit={(event) => void submit(event)} className="flex flex-col gap-3">
          <fieldset className="flex flex-col gap-1">
            <legend className="text-sm font-medium">{t("shelf.export.modeLabel")}</legend>
            <RadioRow
              label={t("shelf.export.modePath")}
              name="export-mode"
              checked={mode === "path"}
              onPick={() => setMode("path")}
            />
            <RadioRow
              label={t("shelf.export.modeZip")}
              name="export-mode"
              checked={mode === "zip"}
              onPick={() => setMode("zip")}
            />
          </fieldset>
          {mode === "path" ? (
            <TextField
              label={t("shelf.export.pathLabel")}
              value={path}
              onChange={setPath}
              isInvalid={pathInvalid}
              validationMessage={pathInvalid ? t("shelf.export.pathRequired") : undefined}
            />
          ) : null}
          {refusal ? <FailureAlert message={refusal} /> : null}
          <button type="submit" disabled={busy} className={PRIMARY_BUTTON}>
            {t("shelf.export.submit")}
          </button>
        </form>
      )}
    </div>
  );
}

/**
 * Import an archive on the shelf: the source is an uploaded file or a path
 * on this machine — exactly one, refused by name when both are given —
 * and the target is a new novel or one picked from the shelf's own list.
 * The answer's report is the dialog's second half: every count class, every
 * conflict as a `file — reason` row, every metadata field the merge left
 * untouched. Conflict names arrive from the archive and render as text
 * nodes, never markup.
 */
export function ImportArchiveDialog({ novels }: { novels: Novel[] }) {
  const t = useTranslation();
  return (
    <Dialog title={t("shelf.importTitle")} triggerLabel={t("shelf.import")}>
      {(close) => <ImportForm novels={novels} close={close} />}
    </Dialog>
  );
}

/** What the dialog refuses before the wire: both sources at once, neither,
 *  or an existing target picked without naming it. */
type FormProblem = "both" | "none" | "target" | null;

type Translate = ReturnType<typeof useTranslation>;

/** The report's count lines, zeros dropped — the page shows all nine, the
 *  one-line announcement carries only the classes that did something. */
function reportSummary(report: ImportReport, t: Translate): string[] {
  const classes: Array<[string, number]> = [
    [t("shelf.report.chaptersNew", { count: report.chapters_new }), report.chapters_new],
    [t("shelf.report.chaptersRevised", { count: report.chapters_revised }), report.chapters_revised],
    [
      t("shelf.report.chaptersUnchanged", { count: report.chapters_already_current }),
      report.chapters_already_current,
    ],
    [t("shelf.report.entitiesNew", { count: report.entities_new }), report.entities_new],
    [t("shelf.report.entitiesRevised", { count: report.entities_revised }), report.entities_revised],
    [t("shelf.report.entitiesRenamed", { count: report.entities_renamed }), report.entities_renamed],
    [
      t("shelf.report.entitiesUnchanged", { count: report.entities_already_current }),
      report.entities_already_current,
    ],
    [t("shelf.report.relationsCreated", { count: report.relations_created }), report.relations_created],
    [
      t("shelf.report.relationsUnchanged", { count: report.relations_already_current }),
      report.relations_already_current,
    ],
  ];
  return classes.filter(([, count]) => count > 0).map(([message]) => message);
}

function ImportForm({ novels, close }: { novels: Novel[]; close: () => void }) {
  const t = useTranslation();
  const [file, setFile] = useState<File | null>(null);
  const [pathText, setPathText] = useState("");
  const [target, setTarget] = useState<"new" | "existing">("new");
  const [targetId, setTargetId] = useState("");
  const [report, setReport] = useState<ImportReport | null>(null);
  const [problem, setProblem] = useState<FormProblem>(null);
  const [refusal, setRefusal] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Resetting a file input is the DOM's job, not React's: the ref is the
  // one door that can empty it after a pick.
  const fileInput = useRef<HTMLInputElement>(null);

  const problemText =
    problem === "both"
      ? t("shelf.import.bothSources")
      : problem === "none"
        ? t("shelf.import.noSource")
        : problem === "target"
          ? t("shelf.import.targetRequired")
          : null;

  /** Drop the picked file from state and from the input itself. */
  function removeFile() {
    setFile(null);
    if (fileInput.current !== null) fileInput.current.value = "";
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    setRefusal(null);
    const hasFile = file !== null;
    const hasPath = pathText.trim() !== "";
    if (hasFile && hasPath) {
      setProblem("both");
      return;
    }
    if (!hasFile && !hasPath) {
      setProblem("none");
      return;
    }
    if (target === "existing" && targetId === "") {
      setProblem("target");
      return;
    }
    setBusy(true);
    try {
      const answer = await importArchive({
        file: hasFile ? file! : undefined,
        path: hasPath ? pathText.trim() : undefined,
        novelId: target === "existing" ? targetId : undefined,
      });
      // The shelf must show what this made: a new novel's row, a merged
      // novel's new "last touched" — the list's key, invalidated once.
      void queryClient.invalidateQueries({ queryKey: ["novels"] });
      // The report replaces the form; a non-visual reader hears the
      // summary, because the form it was typing into just went away.
      setReport(answer);
      announce(
        [t("shelf.report.heading"), ...reportSummary(answer, t)].join(" "),
      );
    } catch (error) {
      const status = (error as InterchangeFailure).status;
      const detail = detailOf(error) as
        | { code?: string; file?: string; reason?: string }
        | undefined;
      if (status === 413) {
        setRefusal(t("shelf.import.tooLarge"));
      } else if (detail?.code === "embedding-mismatch") {
        setRefusal(t("shelf.import.embeddingMismatch"));
      } else if (detail?.code === "archive_invalid") {
        setRefusal(
          t("shelf.import.archiveInvalid", {
            file: detail.file ?? "",
            reason: detail.reason ?? "",
          }),
        );
      } else if (status >= 400 && status < 500) {
        // The server answered and named no fix: a typo path, an archive
        // this build cannot read — not evidence the service is down.
        setRefusal(t("shelf.import.refused"));
      } else {
        setRefusal(t("shelf.import.error"));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-4 flex flex-col gap-3">
      {report ? (
        <ImportReportView report={report} close={close} />
      ) : (
        <form onSubmit={(event) => void submit(event)} className="flex flex-col gap-3">
          {/* Both sources stand on the form at once: whichever is filled
              decides, and a fill on both is refused by name — a picked file
              is never silently dropped in favor of a typed path. */}
          <label className="flex flex-col gap-1 text-sm font-medium">
            {t("shelf.import.fileLabel")}
            <input
              ref={fileInput}
              type="file"
              accept=".zip,application/zip"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              className="rounded-md border border-border bg-card px-3 py-2 text-sm font-normal file:mr-3 file:rounded file:border-0 file:bg-transparent file:text-sm file:font-medium"
            />
          </label>
          {file ? (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted">{file.name}</span>
              <button type="button" onClick={removeFile} className={QUIET_BUTTON}>
                {t("shelf.import.fileRemove")}
              </button>
            </div>
          ) : null}
          <TextField
            label={t("shelf.import.pathLabel")}
            value={pathText}
            onChange={setPathText}
          />
          <fieldset className="flex flex-col gap-1">
            <legend className="text-sm font-medium">{t("shelf.import.targetLabel")}</legend>
            <RadioRow
              label={t("shelf.import.targetNew")}
              name="import-target"
              checked={target === "new"}
              onPick={() => setTarget("new")}
            />
            <RadioRow
              label={t("shelf.import.targetExisting")}
              name="import-target"
              checked={target === "existing"}
              onPick={() => setTarget("existing")}
            />
            {target === "existing" ? (
              <label className="mt-1 flex flex-col gap-1 text-sm font-medium">
                {t("shelf.import.targetNovelLabel")}
                <select
                  value={targetId}
                  onChange={(event) => setTargetId(event.target.value)}
                  className="rounded-md border border-border bg-card px-3 py-2 text-sm font-normal"
                >
                  <option value="">{t("shelf.import.targetPick")}</option>
                  {novels.map((novel) => (
                    <option key={novel.id} value={novel.id}>
                      {novel.title}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
          </fieldset>
          {problemText ? <FailureAlert message={problemText} /> : null}
          {refusal ? <FailureAlert message={refusal} /> : null}
          <button type="submit" disabled={busy} className={PRIMARY_BUTTON}>
            {t("shelf.import.submit")}
          </button>
        </form>
      )}
    </div>
  );
}

/**
 * The import's receipt: all nine count classes (the zeros included — a
 * class the engine carried may not go silent), each refused item as a
 * `file — reason` row, each untouched metadata field named. Every string
 * the archive supplied is interpolated into a message and rendered as a
 * text node; React escapes it, and no attribute ever executes it.
 */
function ImportReportView({ report, close }: { report: ImportReport; close: () => void }) {
  const t = useTranslation();
  const headingId = useId();
  return (
    <div className="flex flex-col gap-3 text-sm">
      <h3 id={headingId} className="font-medium">
        {t("shelf.report.heading")}
      </h3>
      <ul aria-labelledby={headingId} className="flex flex-col gap-1">
        <li>{t("shelf.report.chaptersNew", { count: report.chapters_new })}</li>
        <li>{t("shelf.report.chaptersRevised", { count: report.chapters_revised })}</li>
        <li>{t("shelf.report.chaptersUnchanged", { count: report.chapters_already_current })}</li>
        <li>{t("shelf.report.entitiesNew", { count: report.entities_new })}</li>
        <li>{t("shelf.report.entitiesRevised", { count: report.entities_revised })}</li>
        <li>{t("shelf.report.entitiesRenamed", { count: report.entities_renamed })}</li>
        <li>{t("shelf.report.entitiesUnchanged", { count: report.entities_already_current })}</li>
        <li>{t("shelf.report.relationsCreated", { count: report.relations_created })}</li>
        <li>{t("shelf.report.relationsUnchanged", { count: report.relations_already_current })}</li>
      </ul>
      {report.conflicts.length > 0 ? (
        <section className="flex flex-col gap-1">
          <p className="font-medium">
            {t("shelf.report.conflictsHeading", { count: report.conflicts.length })}
          </p>
          <ul className="flex flex-col gap-1">
            {report.conflicts.map((conflict, index) => (
              <li key={index}>{t("shelf.report.conflictRow", conflict)}</li>
            ))}
          </ul>
        </section>
      ) : null}
      {report.metadata_conflicts.length > 0 ? (
        <section className="flex flex-col gap-1">
          <p className="font-medium">
            {t("shelf.report.metadataHeading", { count: report.metadata_conflicts.length })}
          </p>
          <ul className="flex flex-col gap-1">
            {report.metadata_conflicts.map((field, index) => (
              <li key={index}>{field}</li>
            ))}
          </ul>
        </section>
      ) : null}
      <button type="button" onClick={close} className={QUIET_BUTTON}>
        {t("shelf.report.close")}
      </button>
    </div>
  );
}
