/**
 * The knowledge dock face (W5 Tasks 1/2) — the workspace's dock registry
 * mounts this under the writing workspace's route; the generated table
 * (web/lib/generated/routes.ts) is the one composition point, and this
 * file imports no other capability (rule 1). The face reads the real
 * knowledge API through the shell's query seam:
 *
 * - The findings queue: the pending rows the consistency check filed,
 *   oldest first, each card in the draft's conflict shaping (the warning
 *   rail, the rule badge, the evidence beneath the summary). FindingRead
 *   carries no severity field — every finding IS a consistency conflict,
 *   so the draft's conflict tone stands for all rows; no tier is invented.
 *   Acknowledge and dismiss are the API's two real decisions (the draft's
 *   harmonize buttons are mock rewrites no endpoint serves): each mutates
 *   with an honest pending face on its own card, names its refusal, and
 *   the settled queue refetches — the server's truth, never an optimistic
 *   removal.
 * - The consistency trigger: POST enqueues the whole-novel check (202,
 *   the job lane). The face stands busy — „Prüfung läuft…" — while the
 *   job is outstanding, polls the row (never a connection to the work),
 *   and on the settle refetches the findings: the count then reads the
 *   result. A refused enqueue, a failed job and a dead poll each name
 *   themselves apart from the queue's own outage.
 * - The entity chips (W5 Task 2 — #867 retired; Task 3 wires the door): the
 *   novel's real rows, typed by the extraction contract's vocabulary — the
 *   type is the chip's honest label, the glyph the app's own face for the
 *   concept. The chip is a door now: its click opens the lore graph with the
 *   row selected (the `entity` search param), the dossier the graph panel
 *   shows. The inert-chip interim is retired.
 * - The extraction trigger and its review (W5 Task 2 — #866's family):
 *   POST enqueues the last-written chapter's extraction (202, the same
 *   job lane as the check; the shell's dock fallback picks the chapter,
 *   and the target note names it). The settle refetches the suggestion
 *   queue; each proposal renders as a card with its name, type,
 *   description and proposed relations. Accept creates the entity (the
 *   chips refetch the born row) and announces the relations it could not
 *   place — once, transient (D8); discard consumes the proposal without
 *   creating anything. Both decisions lock their card's two doors
 *   together while one is in flight (the server consumes the row once).
 *
 * The draft's „Verifizierte Entitäten" list is mock data (no per-entity
 * consistency status exists on any model) — the chips carry the row's
 * own name and type, never an invented verified state.
 */
import type { UseMutationResult } from "@tanstack/react-query";
import { useNavigate, useParams } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import type { Accept, Finding, Suggestion } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import {
  activeChapterFallback,
  queryClient,
  useAcceptSuggestion,
  useAcknowledgeFinding,
  useChaptersQuery,
  useDiscardSuggestion,
  useDismissFinding,
  useEnqueueCheck,
  useEnqueueExtraction,
  useEntitiesQuery,
  useFindingsQuery,
  useJobQuery,
  usePendingSuggestionsQuery,
} from "@shell/lib/query";
import { CARD_EYEBROW, FOCUS } from "@shell/ui/card";
import { Icon } from "@shell/ui/icons";

import { entityTypeIcon, entityTypeLabel } from "./entityTypes";
import { relationTypeLabel } from "./relations";

/** One finding card — the draft's conflict geometry on the row's own
 *  words. The two decisions ride the shared mutations; the pending and
 *  refused faces answer per card (the mutation's variables name the row
 *  the ask is for), so one outstanding decision never locks the queue. */
function FindingCard({
  finding,
  t,
  acknowledge,
  dismiss,
}: {
  finding: Finding;
  t: ReturnType<typeof useTranslation>;
  acknowledge: UseMutationResult<Finding, Error, string>;
  dismiss: UseMutationResult<Finding, Error, string>;
}) {
  const ackBusy = acknowledge.isPending && acknowledge.variables === finding.id;
  const dismissBusy = dismiss.isPending && dismiss.variables === finding.id;
  // One outstanding decision locks BOTH doors on its card: the server
  // consumes the finding once, so the sibling click would race the same
  // row into a 409. The busy ink stays on the door whose ask is in flight.
  const busy = ackBusy || dismissBusy;
  const failed =
    (acknowledge.isError && acknowledge.variables === finding.id) ||
    (dismiss.isError && dismiss.variables === finding.id);
  return (
    <li
      data-testid="knowledge-finding"
      className="relative overflow-hidden rounded-lg border border-border bg-panel p-3 shadow-card"
    >
      {/* The draft's severity rail: the conflict's warning ink. No
          severity field exists — the tone is the finding kind's own. */}
      <div data-severity-rail aria-hidden="true" className="absolute bottom-0 left-0 top-0 w-1 bg-warning" />
      <div className="mb-1.5 flex items-start justify-between gap-2 pl-2">
        <h4 className="flex items-start gap-1 text-meta font-semibold text-primary">
          <span className="mt-0.5 shrink-0 text-warning">
            <Icon name="warning" size={13} />
          </span>
          {finding.summary}
        </h4>
        <span className="shrink-0 rounded bg-warning/10 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-warning">
          {t("knowledge.dock.conflict")}
        </span>
      </div>
      {finding.detail !== null && (
        <p className="mb-2 pl-2 text-meta leading-relaxed text-muted">{finding.detail}</p>
      )}
      <div className="flex items-center gap-1.5 pl-2">
        <button
          type="button"
          disabled={busy}
          aria-busy={ackBusy}
          onClick={() => acknowledge.mutate(finding.id)}
          className={`flex items-center gap-1 rounded bg-primary px-2.5 py-1 text-[11px] font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-50 ${FOCUS}`}
        >
          <Icon name="check" size={12} />
          <span>{t("knowledge.dock.acknowledge")}</span>
        </button>
        <button
          type="button"
          disabled={busy}
          aria-busy={dismissBusy}
          onClick={() => dismiss.mutate(finding.id)}
          className={`rounded px-2 py-1 text-[11px] font-medium text-muted transition-colors hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50 ${FOCUS}`}
        >
          {t("knowledge.dock.dismiss")}
        </button>
      </div>
      {failed && (
        <p role="alert" className="mt-1.5 pl-2 text-[11px] text-danger">
          {t("knowledge.dock.actionFailed")}
        </p>
      )}
    </li>
  );
}

/** One suggestion card — the proposal's own words in the finding card's
 *  geometry (a proposal is not a conflict: no warning rail, the type
 *  badge wears neutral ink). The two decisions lock together exactly as
 *  the finding's do — the server consumes the suggestion once. Accept
 *  hands its answer up (the skipped relations are announced once, D8);
 *  discard clears the announcement on its way out. */
function SuggestionCard({
  suggestion,
  t,
  accept,
  discard,
  onAccepted,
  onDiscard,
}: {
  suggestion: Suggestion;
  t: ReturnType<typeof useTranslation>;
  accept: UseMutationResult<Accept, Error, string>;
  discard: UseMutationResult<Suggestion, Error, string>;
  onAccepted: (accepted: Accept) => void;
  onDiscard: () => void;
}) {
  const acceptBusy = accept.isPending && accept.variables === suggestion.id;
  const discardBusy = discard.isPending && discard.variables === suggestion.id;
  const busy = acceptBusy || discardBusy;
  const failed =
    (accept.isError && accept.variables === suggestion.id) ||
    (discard.isError && discard.variables === suggestion.id);
  return (
    <li
      data-testid="knowledge-suggestion"
      className="rounded-lg border border-border bg-panel p-3 shadow-card"
    >
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <span className={CARD_EYEBROW}>{t("knowledge.dock.suggestion")}</span>
        <span className="shrink-0 rounded bg-surface-container-high px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-muted">
          {entityTypeLabel(t, suggestion.type)}
        </span>
      </div>
      <h4 className="text-meta font-semibold text-foreground">{suggestion.name}</h4>
      {suggestion.description !== null && (
        <p className="mt-1 text-meta leading-relaxed text-muted">{suggestion.description}</p>
      )}
      {suggestion.relations.length > 0 && (
        <div className="mt-1.5">
          <span className="text-[10px] font-bold uppercase tracking-wider text-muted">
            {t("knowledge.dock.suggestionRelations")}
          </span>
          <ul className="mt-0.5 space-y-0.5">
            {suggestion.relations.map((relation, index) => (
              <li
                // The index rides the key: a proposal may name the same
                // (target, type) pair twice, and the pair alone would
                // collide — the position makes every row's key its own.
                key={`${relation.target_name}\u0000${relation.relation_type}\u0000${index}`}
                className="text-[11px] text-muted"
              >
                → {relation.target_name} · <span>{relationTypeLabel(t, relation.relation_type)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="mt-2 flex items-center gap-1.5">
        <button
          type="button"
          disabled={busy}
          aria-busy={acceptBusy}
          onClick={() => {
            void accept
              .mutateAsync(suggestion.id)
              .then(onAccepted)
              .catch(() => {
                // The refusal's alert stands on the mutation's own error face.
              });
          }}
          className={`flex items-center gap-1 rounded bg-primary px-2.5 py-1 text-[11px] font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-50 ${FOCUS}`}
        >
          <Icon name="check" size={12} />
          <span>{t("knowledge.dock.accept")}</span>
        </button>
        <button
          type="button"
          disabled={busy}
          aria-busy={discardBusy}
          onClick={() => {
            onDiscard();
            discard.mutate(suggestion.id);
          }}
          className={`rounded px-2 py-1 text-[11px] font-medium text-muted transition-colors hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50 ${FOCUS}`}
        >
          {t("knowledge.dock.discard")}
        </button>
      </div>
      {failed && (
        <p role="alert" className="mt-1.5 text-[11px] text-danger">
          {t("knowledge.dock.actionFailed")}
        </p>
      )}
    </li>
  );
}

/** The outage face one read wears: the named failure and the retry that
 *  asks again — the findings queue's own geometry, shared by the entity
 *  list, the chapter list and the suggestion queue so every outage reads
 *  the same way and names its own answer. */
function OutageFace({ message, onRetry }: { message: string; onRetry: () => void }) {
  const t = useTranslation();
  return (
    <div
      role="alert"
      className="space-y-1.5 rounded-lg border border-danger/40 bg-panel p-3 text-center"
    >
      <p className="text-meta text-danger">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className={`rounded border border-border bg-surface-container-low px-2.5 py-1 text-[11px] font-medium text-foreground transition-colors hover:bg-surface-container ${FOCUS}`}
      >
        {t("knowledge.dock.retry")}
      </button>
    </div>
  );
}

export function KnowledgeDock() {
  const t = useTranslation();
  // The novel is the workspace route's own param — the dock reads the
  // book it stands beside, never a parsed pathname.
  const { novelId } = useParams({ from: "/novels/$novelId" });
  const navigate = useNavigate();
  const findings = useFindingsQuery(novelId);
  const enqueue = useEnqueueCheck(novelId);
  const acknowledge = useAcknowledgeFinding(novelId);
  const dismiss = useDismissFinding(novelId);
  const [checkJobId, setCheckJobId] = useState<string | null>(null);
  const [checkJobFailed, setCheckJobFailed] = useState(false);
  const checkJob = useJobQuery(checkJobId);

  // The entity chips' read: the novel's whole canon, unfiltered — the
  // graph and the dossiers (Tasks 3/5) narrow the same key; the dock
  // names what the book has.
  const entities = useEntitiesQuery(novelId);

  // The extraction's target: the shell's dock fallback — the chapter
  // last written in, from the same cached list the workspace rail reads
  // (one truth, deduped). The target note names it, so the writer sees
  // exactly what the extraction will read; no chapter, no trigger.
  const chapters = useChaptersQuery(novelId);
  const chapterId = activeChapterFallback(chapters.data ?? []);
  const chapter = chapters.data?.find((row) => row.id === chapterId) ?? null;

  const suggestions = usePendingSuggestionsQuery(novelId);
  const extractEnqueue = useEnqueueExtraction(novelId);
  const accept = useAcceptSuggestion(novelId);
  const discard = useDiscardSuggestion(novelId);
  const [extractJobId, setExtractJobId] = useState<string | null>(null);
  const [extractJobFailed, setExtractJobFailed] = useState(false);
  const extractJob = useJobQuery(extractJobId);
  // The accept's skipped relations (D8): announced once, transient —
  // the next decision or extraction clears the note; nothing persists it.
  const [skippedNote, setSkippedNote] = useState<string | null>(null);

  // The honest busy: the enqueue in flight, or a job outstanding whose
  // poll still answers. A dead poll cannot keep the promise of movement
  // — it unlocks the trigger and names itself instead.
  const checkPollFailed = checkJob.isError;
  const checkBusy = enqueue.isPending || (checkJobId !== null && !checkPollFailed);
  const checkFailed = enqueue.isError || checkJobFailed;

  // The settle beat: a done or failed row refetches the pending findings
  // (the check's result IS the queue), and only then does the busy face
  // lift — the count the writer reads next is the refetched truth. The
  // poll retires with the jobId; no timer outlives the answer.
  useEffect(() => {
    const status = checkJob.data?.status;
    if (checkJobId === null || (status !== "done" && status !== "failed")) return;
    let cancelled = false;
    void (async () => {
      await queryClient.invalidateQueries({ queryKey: ["knowledge", "findings", novelId] });
      if (cancelled) return;
      setCheckJobFailed(status === "failed");
      setCheckJobId(null);
    })();
    return () => {
      cancelled = true;
    };
  }, [checkJobId, checkJob.data?.status, novelId]);

  /** Enqueue the check and select its job for polling; a refused enqueue
   *  keeps the trigger live (the lane never heard of it — the retry is
   *  the same button again). */
  async function check() {
    setCheckJobFailed(false);
    try {
      const accepted = await enqueue.mutateAsync();
      setCheckJobId(accepted.job_id);
    } catch {
      // The refusal's alert stands on the mutation's own error face.
    }
  }

  // The extraction lane — the check's own discipline, one job at a time
  // on its own lane: the settle refetches the suggestion queue (the
  // extraction's result IS the proposals), never the entities (only an
  // accept creates one).
  const extractPollFailed = extractJob.isError;
  const extractBusy = extractEnqueue.isPending || (extractJobId !== null && !extractPollFailed);
  const extractFailed = extractEnqueue.isError || extractJobFailed;

  useEffect(() => {
    const status = extractJob.data?.status;
    if (extractJobId === null || (status !== "done" && status !== "failed")) return;
    let cancelled = false;
    void (async () => {
      await queryClient.invalidateQueries({ queryKey: ["knowledge", "suggestions", novelId] });
      if (cancelled) return;
      setExtractJobFailed(status === "failed");
      setExtractJobId(null);
    })();
    return () => {
      cancelled = true;
    };
  }, [extractJobId, extractJob.data?.status, novelId]);

  /** Enqueue the active chapter's extraction; no chapter is a no-op (the
   *  trigger is not offered), a refused enqueue keeps the trigger live. */
  async function extract() {
    if (chapterId === null) return;
    setExtractJobFailed(false);
    setSkippedNote(null);
    try {
      const accepted = await extractEnqueue.mutateAsync({ chapterId });
      setExtractJobId(accepted.job_id);
    } catch {
      // The refusal's alert stands on the mutation's own error face.
    }
  }

  /** The accept's answer: the skipped relations are announced once, in
   *  the locale's own plural, naming the targets accept could not reach.
   *  A clean accept clears any standing note — the note belongs to the
   *  one decision that earned it. */
  function onAccepted(accepted: Accept) {
    const skipped = accepted.skipped_relations;
    setSkippedNote(
      skipped.length > 0
        ? t("knowledge.dock.relationSkipped", {
            count: skipped.length,
            names: skipped.map((skip) => skip.target_name).join(", "),
          })
        : null,
    );
  }

  const count = findings.data?.length ?? 0;
  const entityCount = entities.data?.length ?? 0;

  return (
    <div data-testid="knowledge-dock" className="space-y-3">
      {/* The consistency section — the draft's diagnosis header (the
          eyebrow left, the open count right) and the check's trigger.
          The count is a live region: the settle's result announces
          itself without stealing focus. */}
      <section aria-label={t("knowledge.dock.diagnosis")} className="space-y-2">
        <div className="flex items-center justify-between">
          <span className={CARD_EYEBROW}>{t("knowledge.dock.diagnosis")}</span>
          <span
            role="status"
            className={`text-[11px] font-semibold ${count > 0 ? "text-warning" : "text-muted"}`}
          >
            {findings.isSuccess ? t("knowledge.dock.openCount", { count }) : "—"}
          </span>
        </div>
        <button
          type="button"
          onClick={() => void check()}
          disabled={checkBusy}
          aria-busy={checkBusy}
          className={`flex w-full items-center justify-center gap-1.5 rounded border border-border bg-surface-container-low px-2 py-1.5 text-meta font-medium text-foreground transition-colors hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-60 ${FOCUS}`}
        >
          <Icon name="refresh" size={13} />
          <span>{checkBusy ? t("knowledge.dock.checkBusy") : t("knowledge.dock.check")}</span>
        </button>
        {checkFailed && (
          <p role="alert" className="text-meta text-danger">
            {t("knowledge.dock.checkFailed")}
          </p>
        )}
        {checkPollFailed && !checkFailed && (
          <p role="alert" className="text-meta text-danger">
            {t("knowledge.dock.pollFailed")}
          </p>
        )}
      </section>

      {/* The findings queue — the rows the server files, the honest
          loading, outage and empty faces apart from each other. */}
      {findings.isPending ? (
        <p role="status" className="py-3 text-center text-meta text-muted">
          {t("knowledge.dock.loading")}
        </p>
      ) : findings.isError ? (
        <OutageFace message={t("knowledge.dock.loadFailed")} onRetry={() => void findings.refetch()} />
      ) : findings.data.length === 0 ? (
        <div
          data-testid="knowledge-empty"
          className="space-y-1 rounded-lg border border-border bg-panel py-4 text-center"
        >
          <span className="inline-block text-success">
            <Icon name="checkCircle" size={20} />
          </span>
          <p className="text-meta font-medium text-muted">{t("knowledge.dock.empty")}</p>
          <p className="px-3 text-[10px] text-muted">{t("knowledge.dock.emptyNote")}</p>
        </div>
      ) : (
        <ul className="space-y-2.5">
          {findings.data.map((finding) => (
            <FindingCard
              key={finding.id}
              finding={finding}
              t={t}
              acknowledge={acknowledge}
              dismiss={dismiss}
            />
          ))}
        </ul>
      )}

      {/* The entity chips — the novel's real canon (W5 Task 2; the #867
          spotlight retired). The draft's chip geometry: the type's glyph,
          the row's own name, the type as the honest label. No verified
          state is invented — the row carries none. */}
      <section aria-label={t("knowledge.dock.entities")} className="space-y-2">
        <div className="flex items-center justify-between">
          <span className={CARD_EYEBROW}>{t("knowledge.dock.entities")}</span>
          <span role="status" className="text-[11px] font-semibold text-muted">
            {entities.isSuccess ? t("knowledge.dock.entityCount", { count: entityCount }) : "—"}
          </span>
        </div>
        {entities.isPending ? (
          <p role="status" className="py-1 text-center text-meta text-muted">
            {t("knowledge.dock.entitiesLoading")}
          </p>
        ) : entities.isError ? (
          <OutageFace message={t("knowledge.dock.entitiesFailed")} onRetry={() => void entities.refetch()} />
        ) : entities.data.length === 0 ? (
          <div
            data-testid="knowledge-entities-empty"
            className="space-y-1 rounded-lg border border-border bg-panel py-4 text-center"
          >
            <span className="inline-block text-muted">
              <Icon name="knowledge" size={20} />
            </span>
            <p className="text-meta font-medium text-muted">{t("knowledge.dock.entitiesEmpty")}</p>
            <p className="px-3 text-[10px] text-muted">{t("knowledge.dock.entitiesEmptyNote")}</p>
          </div>
        ) : (
          <ul className="flex flex-wrap gap-1.5">
            {entities.data.map((entity) => (
              // The chip is a door (W5 Task 3 — the inert interim retired):
              // its click opens the lore graph with this row selected, the
              // `entity` search param the graph's dossier reads on arrival.
              <li key={entity.id}>
                <button
                  type="button"
                  data-testid="knowledge-entity-chip"
                  onClick={() =>
                    void navigate({
                      to: "/novels/$novelId/knowledge/graph",
                      params: { novelId },
                      search: { entity: entity.id },
                    })
                  }
                  className={`inline-flex items-center gap-1 rounded-full bg-surface-container-high px-2 py-0.5 text-[11px] transition-colors hover:bg-surface-container-highest ${FOCUS}`}
                >
                  <span className="text-muted">
                    <Icon name={entityTypeIcon(entity.type)} size={12} />
                  </span>
                  <span className="font-medium text-foreground">{entity.name}</span>
                  <span className="text-[10px] text-muted">{entityTypeLabel(t, entity.type)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* The extraction and its review — the trigger rides the check's
          own job lane; the proposals it files stand for review below,
          and the queue outlives the job that filled it (a dock reopened
          later still owes the writer the decisions). */}
      <section aria-label={t("knowledge.dock.extraction")} className="space-y-2">
        <span className={CARD_EYEBROW}>{t("knowledge.dock.extraction")}</span>
        {chapters.isPending ? (
          <p role="status" className="py-1 text-center text-meta text-muted">
            {t("knowledge.dock.chaptersLoading")}
          </p>
        ) : chapters.isError ? (
          <OutageFace message={t("knowledge.dock.chaptersFailed")} onRetry={() => void chapters.refetch()} />
        ) : chapterId === null ? (
          <p className="text-meta text-muted">{t("knowledge.dock.noChapters")}</p>
        ) : (
          <>
            <button
              type="button"
              onClick={() => void extract()}
              disabled={extractBusy}
              aria-busy={extractBusy}
              className={`flex w-full items-center justify-center gap-1.5 rounded border border-border bg-surface-container-low px-2 py-1.5 text-meta font-medium text-foreground transition-colors hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-60 ${FOCUS}`}
            >
              <Icon name="spark" size={13} />
              <span>{extractBusy ? t("knowledge.dock.extractBusy") : t("knowledge.dock.extract")}</span>
            </button>
            {chapter !== null && (
              <p className="text-[10px] text-muted">
                {t("knowledge.dock.extractTarget", { title: chapter.title })}
              </p>
            )}
          </>
        )}
        {extractFailed && (
          <p role="alert" className="text-meta text-danger">
            {t("knowledge.dock.extractFailed")}
          </p>
        )}
        {extractPollFailed && !extractFailed && (
          <p role="alert" className="text-meta text-danger">
            {t("knowledge.dock.extractPollFailed")}
          </p>
        )}

        {suggestions.isPending ? (
          <p role="status" className="py-1 text-center text-meta text-muted">
            {t("knowledge.dock.suggestionsLoading")}
          </p>
        ) : suggestions.isError ? (
          <OutageFace
            message={t("knowledge.dock.suggestionsFailed")}
            onRetry={() => void suggestions.refetch()}
          />
        ) : suggestions.data.length === 0 ? (
          <p data-testid="knowledge-suggestions-empty" className="text-meta text-muted">
            {t("knowledge.dock.suggestionsEmpty")}
          </p>
        ) : (
          <ul className="space-y-2.5">
            {suggestions.data.map((suggestion) => (
              <SuggestionCard
                key={suggestion.id}
                suggestion={suggestion}
                t={t}
                accept={accept}
                discard={discard}
                onAccepted={onAccepted}
                onDiscard={() => setSkippedNote(null)}
              />
            ))}
          </ul>
        )}
        {skippedNote !== null && (
          <p role="status" className="text-[11px] text-muted">
            {skippedNote}
          </p>
        )}
      </section>
    </div>
  );
}
