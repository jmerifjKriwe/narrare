import { useParams, useSearch } from "@tanstack/react-router";
import { useId, useState, useEffect, useRef } from "react";

import { announce } from "@shell/lib/announce";
import { useTranslation } from "@shell/lib/i18n";
import {
  activeChapterFallback,
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

import { entityTypeLabel } from "./entityTypes";
import { relationTypeLabel } from "./relations";
import { useSettleJob } from "./useSettleJob";

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
  // Latch the param-less fallback the way the workbench latches its
  // selection: a dismissed create must not re-target extraction onto the
  // newly created (empty) chapter. The fallback moves only when the
  // latched id leaves the list.
  const [latchedFallback, setLatchedFallback] = useState<string | null>(null);
  const novelRef = useRef(novelId);
  useEffect(() => {
    const rows = chapters.data;
    if (rows === undefined) return;
    setLatchedFallback((previous) => {
      // A novel switch invalidates the latch: the previous novel's chapter
      // must never survive as the fallback for the new one.
      if (novelRef.current !== novelId) {
        novelRef.current = novelId;
        return activeChapterFallback(rows);
      }
      return previous !== null && rows.some((chapter) => chapter.id === previous)
        ? previous
        : activeChapterFallback(rows);
    });
  }, [chapters.data, novelId]);
  const chapterId =
    chapterParam !== undefined && (chapters.data ?? []).some((chapter) => chapter.id === chapterParam)
      ? chapterParam
      : latchedFallback ?? activeChapterFallback(chapters.data ?? []);
  const [jobId, setJobId] = useState<string | null>(null);
  const [enqueueFailed, setEnqueueFailed] = useState(false);
  const job = useJobQuery(jobId);
  const enqueue = useEnqueueExtraction(novelId);
  const suggestions = usePendingSuggestionsQuery(novelId);
  const accept = useAcceptSuggestion(novelId);
  const discard = useDiscardSuggestion(novelId);
  const headingId = useId();

  // The settle beat is the shared hook's: the settled row refetches the
  // pending queue, the dead poll reopens the trigger — one extraction at
  // a time, the same rule the check and the palette's dialogs keep.
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
            {/* The card's own name and its relations block read as
                headings (#314): under ProposalCard's h3 title they step
                h4 → h5, so heading navigation reaches them. */}
            <h4 className="mt-2 text-body font-medium">
              {suggestion.name} · {entityTypeLabel(t, suggestion.type)}
            </h4>
            {suggestion.relations.length > 0 ? (
              // The proposals ride the card (D9): the target's name and
              // the suggested type, the vocabulary's wording or the raw
              // proposal's own words.
              <div className="mt-2">
                <h5 className="text-body font-medium">
                  {t("knowledge.suggestionRelationsHeading")}
                </h5>
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
