import { useParams, useSearch } from "@tanstack/react-router";
import { useEffect, useId, useState } from "react";

import { announce } from "@shell/lib/announce";
import { useTranslation } from "@shell/lib/i18n";
import {
  activeChapterFallback,
  queryClient,
  useAcceptSuggestion,
  useChaptersQuery,
  useDiscardSuggestion,
  useEnqueueExtraction,
  useJobQuery,
  usePendingSuggestionsQuery,
} from "@shell/lib/query";
import { Button } from "@shell/ui/Button";
import { JobStatus } from "@shell/ui/JobStatus";
import { Notice } from "@shell/ui/Notice";
import { ProposalCard } from "@shell/ui/ProposalCard";

import { entityTypeLabel } from "./EntitiesPanel";
import { relationTypeLabel } from "./relations";

/** Extraction and its review: the chapter the editor is showing, through
 *  the job lane, and the queue its result files — one proposal card per
 *  suggested entity. */
export function ExtractionPanel() {
  const t = useTranslation();
  const { id: novelId } = useParams({ from: "/novels/$id" });
  // The chapter is the editor's, and the selection's address is the URL:
  // the panel reads the workspace's own chapter param, and when the
  // address names none — the param-less workbench, where the editor shows
  // the last chapter written in — it falls back to that same chapter, from
  // the same cached list (the answer is deduped with the workbench's own
  // read). One truth, so extraction asks for exactly what the editor
  // shows, and nothing is written to the URL for it.
  const { chapter: chapterParam } = useSearch({ from: "/novels/$id" });
  const chapters = useChaptersQuery(novelId);
  const chapterId = chapterParam ?? activeChapterFallback(chapters.data ?? []);
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

  // The poll can fail like any fetch: the service going down under an
  // outstanding job leaves the row's answer missing. A missing answer is
  // an error, not a promise of movement — the queued/running row promised
  // progress, and an unanswered poll must not wear that promise.
  const pollFailed = jobId !== null && job.isError;

  // One extraction at a time: the trigger stays closed while its enqueue
  // POST is in flight or the job it filed is still outstanding, because a
  // second click would stack a duplicate job and a duplicate review queue
  // behind the first. Three things hand the button back: a settled row
  // (done or failed is an answer), a poll that met the dead service — an
  // unanswered poll used to count as outstanding, so an unknown state
  // locked the trigger for the whole outage; the locked button was the
  // bug, and the reopened one is the retry — and a refused enqueue: the
  // retry is the same button again, starting a fresh extraction (the
  // outstanding job stays on the durable lane and will run when the
  // service returns, so its suggestions surface in the queue like any
  // run's).
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
    <section aria-labelledby={headingId}>
      <h3 id={headingId} className="text-body font-semibold">
        {t("knowledge.extractionHeading")}
      </h3>
      {chapterId === null ? (
        <p className="mt-2 text-body text-muted">{t("knowledge.noActiveChapter")}</p>
      ) : (
        <div className="mt-2">
          <Button variant="secondary" onClick={() => void extract()} disabled={busy}>
            {t("knowledge.extractChapter")}
          </Button>
        </div>
      )}
      {enqueueFailed ? (
        <Notice tone="danger" live="alert" className="mt-2">
          {t("knowledge.extractionError")}
        </Notice>
      ) : null}
      {job.data && !(pollFailed && (job.data.status === "queued" || job.data.status === "running")) ? (
        // The last-known row renders only what it can still stand behind.
        // A done or failed row is a fact and stays beside the outage's
        // alert; a queued or running row is a promise of movement, and a
        // dead poll cannot keep that promise — hidden, because the alert
        // is the truth and a row still promising progress the panel
        // cannot show would outshout it.
        <div className="mt-2">
          <JobStatus job={job.data} />
        </div>
      ) : null}
      {pollFailed ? (
        // The failed poll names itself where the trigger it unlocked sits:
        // the outage reads as an outage, and the retry is one click away.
        <Notice tone="danger" live="alert" className="mt-2">
          {t("knowledge.errorJob")}
        </Notice>
      ) : null}
      {/* The review queue outlives the job that filled it: a dock reopened
          later still owes the writer the decisions, so the cards render from
          the query, not from the job's lifecycle. The card is the review's
          own surface (P17's to restyle): consumed as it stands, with the
          proposal's name, type and relations riding it. */}
      {suggestions.isError ? (
        // The queue's own outage, named apart from the entity list's (the
        // two panels share the dock, and both queries fail together — a
        // writer reading two alerts must know which answer is missing).
        // Silence here would read as a spent queue, the same mask the
        // entity list shed in its own outage test.
        <Notice tone="danger" live="alert" className="mt-2">
          {t("knowledge.errorQueue")}
        </Notice>
      ) : (
        (suggestions.data ?? []).map((suggestion) => (
          <ProposalCard
            key={suggestion.id}
            titleKey="knowledge.suggestionTitle"
            body={suggestion.description ?? ""}
            onAccept={() => {
              void accept
                .mutateAsync(suggestion.id)
                .then((accepted) => {
                  // The skips are transient (D8): announced once, aloud,
                  // naming the targets accept could not reach — persisted
                  // nowhere, so the announcement is the whole trace.
                  const skipped = accepted.skipped_relations;
                  if (skipped.length > 0) {
                    announce(
                      t("knowledge.relationSkipped", {
                        count: skipped.length,
                        names: skipped.map((skip) => skip.target_name).join(", "),
                      }),
                    );
                  }
                })
                .catch(() => undefined);
            }}
            onDiscard={() => {
              void discard.mutateAsync(suggestion.id).catch(() => undefined);
            }}
          >
            <p className="mt-2 text-body font-medium">
              {suggestion.name} · {entityTypeLabel(t, suggestion.type)}
            </p>
            {suggestion.relations.length > 0 ? (
              // The proposals ride the card (D9): the target's name and
              // the suggested type, the vocabulary's wording or the raw
              // proposal's own words.
              <div className="mt-2">
                <p className="text-body font-medium">
                  {t("knowledge.suggestionRelationsHeading")}
                </p>
                <ul className="mt-1 flex flex-col gap-0.5">
                  {suggestion.relations.map((relation) => (
                    <li
                      key={`${relation.target_name}\u0000${relation.relation_type}`}
                      className="text-body text-muted"
                    >
                      → {relation.target_name} · {relationTypeLabel(t, relation.relation_type)}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </ProposalCard>
        ))
      )}
    </section>
  );
}
