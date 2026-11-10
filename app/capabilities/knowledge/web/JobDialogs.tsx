import { useState } from "react";

import { useTranslation } from "@shell/lib/i18n";
import {
  activeChapterFallback,
  useChaptersQuery,
  useEnqueueCheck,
  useEnqueueExtraction,
  useJobQuery,
} from "@shell/lib/query";
import { Button } from "@shell/ui/Button";
import { Dialog } from "@shell/ui/Dialog";
import { JobStatus } from "@shell/ui/JobStatus";
import { Notice } from "@shell/ui/Notice";

import { useSettleJob } from "./useSettleJob";

/**
 * The extraction behind the palette's row: the chapter the editor is
 * showing, the same enqueue the dock panel owns, the job's row through
 * `JobStatus`. A refused enqueue is named where the retry stands — the
 * trigger itself — never a silent close. The dialog carries no trigger of
 * its own: the palette's modal slot mounts it already open, the row having
 * been the press.
 */
export function ExtractionJobDialog({
  novelId,
  chapterId = null,
  isOpen,
  onOpenChange,
}: {
  novelId: string;
  chapterId?: string | null;
  isOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const t = useTranslation();
  return (
    <Dialog title={t("knowledge.extractionHeading")} isOpen={isOpen} onOpenChange={onOpenChange}>
      {(close) => <ExtractionForm novelId={novelId} chapterId={chapterId} close={close} />}
    </Dialog>
  );
}

/** The whole-novel check behind the palette's row: one trigger, the job's
 *  row, the refusal in words — the dock panel's lane without the dock. */
export function ConsistencyCheckDialog({
  novelId,
  isOpen,
  onOpenChange,
}: {
  novelId: string;
  isOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const t = useTranslation();
  return (
    <Dialog title={t("knowledge.checksHeading")} isOpen={isOpen} onOpenChange={onOpenChange}>
      {(close) => <ConsistencyCheckForm novelId={novelId} close={close} />}
    </Dialog>
  );
}

/** Mounted fresh on every open: the job, the refusal and the busy flag are
 *  this dialog's own, never a previous one's leftovers. */
function ExtractionForm({
  novelId,
  chapterId: chapterProp,
  close,
}: {
  novelId: string;
  chapterId: string | null;
  close: () => void;
}) {
  const t = useTranslation();
  // The chapter is the editor's: the palette hands the one its route carried
  // when the row ran, and without one — the row from a param-less address —
  // the dialog stands on the same fallback the dock panel stands on, the
  // last chapter written in from the same cached list the workbench already
  // asked for. Same precedence as the dock: the prop first, then the fallback.
  const chapters = useChaptersQuery(novelId);
  const chapterId = chapterProp ?? activeChapterFallback(chapters.data ?? []);
  // The target the dialog names: the row the id resolves to, unnamed chapters
  // under the rail's own placeholder — the same words the palette's chapter
  // rows wear.
  const chapter = (chapters.data ?? []).find((row) => row.id === chapterId) ?? null;
  const title =
    chapter === null ? null : chapter.title || t("chapters.defaultTitle", { n: chapter.position + 1 });
  const [jobId, setJobId] = useState<string | null>(null);
  const [enqueueFailed, setEnqueueFailed] = useState(false);
  const job = useJobQuery(jobId);
  const enqueue = useEnqueueExtraction(novelId);

  // The settle beat is the shared hook's: the settled row refetches the
  // pending suggestions — the same beat the dock panel refetches on.
  const { busy, pollFailed } = useSettleJob({
    jobId,
    status: job.data?.status,
    pollError: job.isError,
    enqueuePending: enqueue.isPending,
    novelId,
    queue: "suggestions",
  });

  /** Enqueue the active chapter for polling; no selection is a no-op and failures stay visible. */
  async function extract() {
    if (chapterId === null) return;
    setEnqueueFailed(false);
    try {
      const accepted = await enqueue.mutateAsync({ chapterId });
      setJobId(accepted.job_id);
    } catch {
      // The enqueue itself failed — the job lane never heard of it, so the
      // queue is untouched and the retry is the same button again.
      setEnqueueFailed(true);
    }
  }

  return (
    <div className="mt-4 flex flex-col gap-3">
      {chapterId === null ? (
        <p className="text-body text-muted">{t("knowledge.noActiveChapter")}</p>
      ) : (
        <>
          {title === null ? null : (
            <p className="text-body text-muted">{t("knowledge.extractionTarget", { title })}</p>
          )}
          <Button variant="primary" onClick={() => void extract()} disabled={busy}>
            {t("knowledge.extractChapter")}
          </Button>
        </>
      )}
      {enqueueFailed ? (
        <Notice tone="danger" live="alert">
          {t("knowledge.extractionError")}
        </Notice>
      ) : null}
      {job.data && !(pollFailed && (job.data.status === "queued" || job.data.status === "running")) ? (
        <div>
          <JobStatus job={job.data} />
        </div>
      ) : null}
      {pollFailed ? (
        <Notice tone="danger" live="alert">
          {t("knowledge.errorJob")}
        </Notice>
      ) : null}
      <Button variant="secondary" className="self-start" onClick={close}>
        {t("knowledge.entityCancel")}
      </Button>
    </div>
  );
}

/** Mounted fresh on every open, like the extraction's form. */
function ConsistencyCheckForm({ novelId, close }: { novelId: string; close: () => void }) {
  const t = useTranslation();
  const [jobId, setJobId] = useState<string | null>(null);
  const [enqueueFailed, setEnqueueFailed] = useState(false);
  const job = useJobQuery(jobId);
  const enqueue = useEnqueueCheck(novelId);

  // The settle beat is the shared hook's: the settled row refetches the
  // pending findings — the same beat the dock panel refetches on.
  const { busy, pollFailed } = useSettleJob({
    jobId,
    status: job.data?.status,
    pollError: job.isError,
    enqueuePending: enqueue.isPending,
    novelId,
    queue: "findings",
  });

  /** Enqueue a check and select its job for polling, or expose the enqueue failure. */
  async function check() {
    setEnqueueFailed(false);
    try {
      const accepted = await enqueue.mutateAsync();
      setJobId(accepted.job_id);
    } catch {
      // The enqueue itself failed — the job lane never heard of it, so the
      // queue is untouched and the retry is the same button again.
      setEnqueueFailed(true);
    }
  }

  return (
    <div className="mt-4 flex flex-col gap-3">
      <Button variant="primary" onClick={() => void check()} disabled={busy}>
        {t("knowledge.checkNovel")}
      </Button>
      {enqueueFailed ? (
        <Notice tone="danger" live="alert">
          {t("knowledge.checkError")}
        </Notice>
      ) : null}
      {job.data && !(pollFailed && (job.data.status === "queued" || job.data.status === "running")) ? (
        <div>
          <JobStatus job={job.data} />
        </div>
      ) : null}
      {pollFailed ? (
        <Notice tone="danger" live="alert">
          {t("knowledge.errorCheckJob")}
        </Notice>
      ) : null}
      <Button variant="secondary" className="self-start" onClick={close}>
        {t("knowledge.entityCancel")}
      </Button>
    </div>
  );
}
