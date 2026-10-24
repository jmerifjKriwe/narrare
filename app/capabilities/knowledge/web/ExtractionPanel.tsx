import { useParams } from "@tanstack/react-router";
import { useEffect, useId, useState } from "react";

import { activeChapter, subscribeActiveChapter } from "@shell/lib/activeChapter";
import { useTranslation } from "@shell/lib/i18n";
import {
  queryClient,
  useAcceptSuggestion,
  useDiscardSuggestion,
  useEnqueueExtraction,
  useJobQuery,
  usePendingSuggestionsQuery,
} from "@shell/lib/query";
import { JobStatus } from "@shell/ui/JobStatus";
import { ProposalCard } from "@shell/ui/ProposalCard";

import { entityKindLabel } from "./EntitiesPanel";

/** Extraction and its review: the chapter the editor is showing, through
 *  the job lane, and the queue its result files — one proposal card per
 *  suggested entity. */
export function ExtractionPanel() {
  const t = useTranslation();
  const { id: novelId } = useParams({ from: "/novels/$id" });
  // The chapter is the editor's, not the dock's: the workspace publishes
  // its selection through the shell seam, and the panel reads it on mount
  // (the dock opens after the selection happened) and on every change.
  const [chapterId, setChapterId] = useState<string | null>(activeChapter());
  useEffect(() => subscribeActiveChapter(setChapterId), []);
  const [jobId, setJobId] = useState<string | null>(null);
  const [enqueueFailed, setEnqueueFailed] = useState(false);
  const job = useJobQuery(jobId);
  const enqueue = useEnqueueExtraction(novelId);
  const suggestions = usePendingSuggestionsQuery(novelId);
  const accept = useAcceptSuggestion(novelId);
  const discard = useDiscardSuggestion(novelId);
  const headingId = useId();

  // The settled job decides the queue: the row turning done or failed is
  // the moment the suggestions exist (or provably will not), so that is
  // when the pending queue refetches — the poll publishes its own finding.
  const settled = job.data?.status === "done" || job.data?.status === "failed";
  useEffect(() => {
    if (!settled) return;
    void queryClient.invalidateQueries({ queryKey: ["knowledge", "suggestions", novelId] });
  }, [settled, novelId]);

  // One extraction at a time: the trigger stays closed while its enqueue
  // POST is in flight or the job it filed is still outstanding (settled is
  // false until done or failed — an unanswered poll counts as outstanding,
  // so an unknown state never reopens the button), because a second click
  // would stack a duplicate job and a duplicate review queue behind the
  // first. A settled job hands the button back, and so does a refused
  // enqueue: the retry is the same button again.
  const busy = enqueue.isPending || (jobId !== null && !settled);

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
    <section aria-labelledby={headingId}>
      <h3 id={headingId} className="text-sm font-semibold">
        {t("knowledge.extractionHeading")}
      </h3>
      {chapterId === null ? (
        <p className="mt-2 text-sm text-muted">{t("knowledge.noActiveChapter")}</p>
      ) : (
        <button
          type="button"
          onClick={() => void extract()}
          disabled={busy}
          className="mt-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:cursor-not-allowed disabled:opacity-50"
        >
          {t("knowledge.extractChapter")}
        </button>
      )}
      {enqueueFailed ? (
        <p role="alert" className="mt-2 text-sm text-danger">
          {t("knowledge.extractionError")}
        </p>
      ) : null}
      {job.data ? (
        <div className="mt-2">
          <JobStatus job={job.data} />
        </div>
      ) : null}
      {/* The review queue outlives the job that filled it: a dock reopened
          later still owes the writer the decisions, so the cards render from
          the query, not from the job's lifecycle. */}
      {(suggestions.data ?? []).map((suggestion) => (
        <ProposalCard
          key={suggestion.id}
          titleKey="knowledge.suggestionTitle"
          body={suggestion.description ?? ""}
          onAccept={() => {
            void accept.mutateAsync(suggestion.id).catch(() => undefined);
          }}
          onDiscard={() => {
            void discard.mutateAsync(suggestion.id).catch(() => undefined);
          }}
        >
          <p className="mt-2 text-sm font-medium">
            {suggestion.name} · {entityKindLabel(t, suggestion.kind)}
          </p>
        </ProposalCard>
      ))}
    </section>
  );
}
