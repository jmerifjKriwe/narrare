import { useEffect, useState } from "react";

import { useTranslation } from "@shell/lib/i18n";
import {
  activeChapterFallback,
  queryClient,
  useChaptersQuery,
  useEnqueueCheck,
  useEnqueueExtraction,
  useJobQuery,
} from "@shell/lib/query";
import { Button } from "@shell/ui/Button";
import { Dialog } from "@shell/ui/Dialog";
import { JobStatus } from "@shell/ui/JobStatus";
import { Notice } from "@shell/ui/Notice";

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
  isOpen,
  onOpenChange,
}: {
  novelId: string;
  isOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const t = useTranslation();
  return (
    <Dialog title={t("knowledge.extractionHeading")} isOpen={isOpen} onOpenChange={onOpenChange}>
      {(close) => <ExtractionForm novelId={novelId} close={close} />}
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
function ExtractionForm({ novelId, close }: { novelId: string; close: () => void }) {
  const t = useTranslation();
  // The chapter is the editor's: the panel reads the workspace's chapter
  // param first and falls back to the last chapter written in — the dialog
  // has no route param of its own, so it stands on the fallback alone, the
  // same cached list the workbench already asked for.
  const chapters = useChaptersQuery(novelId);
  const chapterId = activeChapterFallback(chapters.data ?? []);
  const [jobId, setJobId] = useState<string | null>(null);
  const [enqueueFailed, setEnqueueFailed] = useState(false);
  const job = useJobQuery(jobId);
  const enqueue = useEnqueueExtraction(novelId);

  // The settled job decides the queue: the row turning done or failed is
  // the moment the pending suggestions exist (or provably will not) — the
  // same beat the dock panel refetches on.
  const settled = job.data?.status === "done" || job.data?.status === "failed";
  useEffect(() => {
    if (!settled) return;
    void queryClient.invalidateQueries({ queryKey: ["knowledge", "suggestions", novelId] });
  }, [settled, novelId]);

  // The poll can fail like any fetch: an unanswered poll is an error, not
  // a promise of movement — the same reading the dock panel keeps.
  const pollFailed = jobId !== null && job.isError;

  // One extraction at a time: the trigger stays closed while its enqueue
  // POST is in flight or the job it filed is still outstanding — the
  // panel's single-shot rule, unchanged. The same three things hand the
  // button back: a settled row, a poll that met the dead service, a
  // refused enqueue.
  const busy = enqueue.isPending || (jobId !== null && !settled && !pollFailed);

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
        <Button variant="primary" onClick={() => void extract()} disabled={busy}>
          {t("knowledge.extractChapter")}
        </Button>
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

  // The settled job decides the queue: the row turning done or failed is
  // the moment the findings exist (or provably will not) — the same beat
  // the dock panel refetches on.
  const settled = job.data?.status === "done" || job.data?.status === "failed";
  useEffect(() => {
    if (!settled) return;
    void queryClient.invalidateQueries({ queryKey: ["knowledge", "findings", novelId] });
  }, [settled, novelId]);

  // The poll can fail like any fetch: an unanswered poll is an error, not
  // a promise of movement — the same reading the dock panel keeps.
  const pollFailed = jobId !== null && job.isError;

  // One check at a time: the trigger stays closed while its enqueue POST
  // is in flight or the job it filed is still outstanding — the panel's
  // single-shot rule, unchanged.
  const busy = enqueue.isPending || (jobId !== null && !settled && !pollFailed);

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
