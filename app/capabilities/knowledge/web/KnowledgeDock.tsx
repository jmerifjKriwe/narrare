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
 *   with an honest pending face on its own card — faces the dock keeps
 *   per row, because the shared mutation observer names only the last
 *   call, and two cards deciding at once would repaint the first idle
 *   while its ask still flies. A refusal names its own row alone, and
 *   the settled queue refetches — the server's truth, never an optimistic
 *   removal.
 * - The consistency trigger: POST enqueues the whole-novel check (202,
 *   the job lane). The lane belongs to the session, not the mount: the
 *   outstanding job id lives at module scope keyed by novel, so a dock
 *   closed mid-job resumes the busy face when it reopens (the API offers
 *   no way to list a novel's running jobs — only a known id answers).
 *   The face stands busy — „Prüfung läuft…" — while the job is
 *   outstanding, polls the row (never a connection to the work), and on
 *   the settle refetches the findings: the count then reads the result.
 *   A refused enqueue and a failed job each name themselves apart from
 *   the queue's own outage. A dead poll unlocks the trigger and names
 *   itself — and while the lane still holds that job, the trigger RESUMES
 *   the poll instead of enqueueing again: a fresh check would pile onto
 *   work the server may already be running, and nothing refuses it
 *   server-side. Only a settled failure — or a poll that answered 404,
 *   the job row itself destroyed under the session, where no resume
 *   could ever answer — clears the lane; the next click after either
 *   is a fresh enqueue, as it should be.
 * - The entity chips (W5 Task 2 — #867 retired): the novel's real rows,
 *   typed by the extraction contract's vocabulary — the type is the
 *   chip's honest label, the glyph the app's own face for the concept.
 *   The chip is a label, not a door: its click target (the dossier panel)
 *   is Task 3/5's surface, so no affordance is offered until the route
 *   exists — no disabled promise.
 * - The extraction trigger and its review (W5 Task 2 — #866's family):
 *   POST enqueues the last-written chapter's extraction (202, its own job
 *   lane under the check's session discipline — the shell's dock fallback
 *   picks the chapter, and the target note names it). The settle refetches
 *   the suggestion queue; each proposal renders as a card with its name,
 *   type, description and proposed relations. Accept creates the entity
 *   (the chips refetch the born row) and announces the relations it could
 *   not place — once, transient (D8); discard consumes the proposal
 *   without creating anything. Both decisions lock their card's two doors
 *   together while one is in flight (the server consumes the row once),
 *   with the same per-row faces as the findings — concurrency repaints
 *   no card idle, and a refusal names its own row.
 *
 * The draft's „Verifizierte Entitäten" list is mock data (no per-entity
 * consistency status exists on any model) — the chips carry the row's
 * own name and type, never an invented verified state.
 */
import { useParams } from "@tanstack/react-router";
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

/** The session's job lanes, keyed by novel: the outstanding check and
 *  extraction job ids a dock adopted. The map lives at module scope on
 *  purpose — the lane is the session's, not the mount's: a dock closed
 *  mid-job must not orphan its poll (a reopened dock would read an idle
 *  trigger and enqueue a second job onto work the server may already be
 *  running, and the API offers no way to list a novel's running jobs —
 *  only a known id answers). A settled lane clears its entry; the map
 *  holds nothing but ids. */
const sessionLanes = new Map<string, { check: string | null; extract: string | null }>();

/** The lane's outstanding job id, or null when the novel's lane is idle. */
function laneJob(novelId: string, lane: "check" | "extract"): string | null {
  return sessionLanes.get(novelId)?.[lane] ?? null;
}

/** Adopt (or clear) the lane's job id — module scope and component state
 *  move together, so a remount picks the lane up where it stands. */
function setLaneJob(novelId: string, lane: "check" | "extract", jobId: string | null): void {
  const lanes = sessionLanes.get(novelId) ?? { check: null, extract: null };
  sessionLanes.set(novelId, { ...lanes, [lane]: jobId });
}

/** The poll's one unrecoverable failure: the job row itself is gone.
 *  The server answers a dead id with a 404 — destroyed under the
 *  session, or another user's — and no resume can ever settle such a
 *  lane; every click would re-ask a door that cannot answer, so the
 *  lane clears instead and the next click enqueues fresh. 5xx and
 *  network failures keep the resume contract: the job may still live
 *  server-side. The status rides the query's throw (the novel read's
 *  own carry); a network failure throws before any status exists and
 *  carries none. */
function jobGone(error: unknown): boolean {
  return (error as { status?: number } | null | undefined)?.status === 404;
}

/** The per-row faces of one shared decision. TanStack's mutation observer
 *  holds only the last call's variables, so two rows deciding at once
 *  would repaint the first as idle while its ask still flies — and its
 *  unlocked door would race the same row a second time. The dock keeps
 *  its own truth instead: a pending set entered when the ask leaves and
 *  left when its answer lands, and a refused set that names the row the
 *  refusal belongs to (cleared by that row's next attempt, never by
 *  another row's). */
function useDecisionRows() {
  const [pending, setPending] = useState<ReadonlySet<string>>(() => new Set());
  const [refused, setRefused] = useState<ReadonlySet<string>>(() => new Set());

  /** The ask leaves for one row: busy from here until its own answer. */
  function begin(rowId: string): void {
    setPending((rows) => (rows.has(rowId) ? rows : new Set(rows).add(rowId)));
    setRefused((rows) => {
      if (!rows.has(rowId)) return rows;
      const next = new Set(rows);
      next.delete(rowId);
      return next;
    });
  }

  /** The answer landed for one row: busy lifts, and only this row's
   *  refusal face follows the verdict. */
  function settle(rowId: string, ok: boolean): void {
    setPending((rows) => {
      if (!rows.has(rowId)) return rows;
      const next = new Set(rows);
      next.delete(rowId);
      return next;
    });
    setRefused((rows) => {
      if (ok ? !rows.has(rowId) : rows.has(rowId)) return rows;
      const next = new Set(rows);
      if (ok) next.delete(rowId);
      else next.add(rowId);
      return next;
    });
  }

  return { pending, refused, begin, settle };
}

/** One finding card — the draft's conflict geometry on the row's own
 *  words. The two decisions' faces arrive per card from the dock's own
 *  per-row truth (never the shared observer's single variables slot), so
 *  one outstanding decision never locks the queue and two at once
 *  repaint neither idle. */
function FindingCard({
  finding,
  t,
  ackBusy,
  dismissBusy,
  failed,
  onAcknowledge,
  onDismiss,
}: {
  finding: Finding;
  t: ReturnType<typeof useTranslation>;
  ackBusy: boolean;
  dismissBusy: boolean;
  failed: boolean;
  onAcknowledge: (findingId: string) => void;
  onDismiss: (findingId: string) => void;
}) {
  // One outstanding decision locks BOTH doors on its card: the server
  // consumes the finding once, so the sibling click would race the same
  // row into a 409. The busy ink stays on the door whose ask is in flight.
  const busy = ackBusy || dismissBusy;
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
          onClick={() => onAcknowledge(finding.id)}
          className={`flex items-center gap-1 rounded bg-primary px-2.5 py-1 text-[11px] font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-50 ${FOCUS}`}
        >
          <Icon name="check" size={12} />
          <span>{t("knowledge.dock.acknowledge")}</span>
        </button>
        <button
          type="button"
          disabled={busy}
          aria-busy={dismissBusy}
          onClick={() => onDismiss(finding.id)}
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
 *  the finding's do — the server consumes the suggestion once — with the
 *  same per-row faces: concurrency repaints no card idle, and a refusal
 *  names its own row. Accept's answer is the dock's (the skipped
 *  relations are announced once, D8); discard's clears the note on its
 *  way out. */
function SuggestionCard({
  suggestion,
  t,
  acceptBusy,
  discardBusy,
  failed,
  onAccept,
  onDiscard,
}: {
  suggestion: Suggestion;
  t: ReturnType<typeof useTranslation>;
  acceptBusy: boolean;
  discardBusy: boolean;
  failed: boolean;
  onAccept: (suggestionId: string) => void;
  onDiscard: (suggestionId: string) => void;
}) {
  const busy = acceptBusy || discardBusy;
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
          onClick={() => onAccept(suggestion.id)}
          className={`flex items-center gap-1 rounded bg-primary px-2.5 py-1 text-[11px] font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-50 ${FOCUS}`}
        >
          <Icon name="check" size={12} />
          <span>{t("knowledge.dock.accept")}</span>
        </button>
        <button
          type="button"
          disabled={busy}
          aria-busy={discardBusy}
          onClick={() => onDiscard(suggestion.id)}
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
  const findings = useFindingsQuery(novelId);
  const enqueue = useEnqueueCheck(novelId);
  const acknowledge = useAcknowledgeFinding(novelId);
  const dismiss = useDismissFinding(novelId);
  // The decisions' per-row faces: the observer's own isPending/variables
  // pair cannot answer "which rows are busy" under concurrency, so the
  // dock enters and settles its own rows around each mutateAsync.
  const ackRows = useDecisionRows();
  const dismissRows = useDecisionRows();

  /** Acknowledge one finding — the row's face enters before the ask
   *  leaves and settles when its own answer lands. */
  async function acknowledgeFinding(findingId: string): Promise<void> {
    ackRows.begin(findingId);
    try {
      await acknowledge.mutateAsync(findingId);
      ackRows.settle(findingId, true);
    } catch {
      ackRows.settle(findingId, false);
    }
  }

  /** Dismiss one finding, on its row's own face. */
  async function dismissFinding(findingId: string): Promise<void> {
    dismissRows.begin(findingId);
    try {
      await dismiss.mutateAsync(findingId);
      dismissRows.settle(findingId, true);
    } catch {
      dismissRows.settle(findingId, false);
    }
  }

  // The lane adopts the session's outstanding job on mount (null when
  // idle), so a dock closed mid-job resumes the busy face when it
  // reopens instead of offering an idle trigger over running work.
  const [checkJobId, setCheckJobId] = useState<string | null>(() => laneJob(novelId, "check"));
  const [checkJobFailed, setCheckJobFailed] = useState(false);
  const checkJob = useJobQuery(checkJobId);

  /** Adopt the check's job for polling — the session lane and the mount
   *  move together. */
  function adoptCheckJob(jobId: string): void {
    setLaneJob(novelId, "check", jobId);
    setCheckJobId(jobId);
  }

  // The honest busy: the enqueue in flight, or a job outstanding whose
  // poll still answers. A dead poll cannot keep the promise of movement
  // — it unlocks the trigger and names itself instead.
  const checkPollFailed = checkJob.isError;
  const checkBusy = enqueue.isPending || (checkJobId !== null && !checkPollFailed);
  const checkFailed = enqueue.isError || checkJobFailed;

  // The settle beat: a done or failed row refetches the pending findings
  // (the check's result IS the queue), and only then does the busy face
  // lift — the count the writer reads next is the refetched truth. The
  // lane retires with the jobId; no timer outlives the answer. A dock
  // closed before the settle cancels only the state writes: the lane
  // keeps the id, and the reopened dock re-runs this beat.
  useEffect(() => {
    const status = checkJob.data?.status;
    if (checkJobId === null || (status !== "done" && status !== "failed")) return;
    let cancelled = false;
    void (async () => {
      await queryClient.invalidateQueries({ queryKey: ["knowledge", "findings", novelId] });
      if (cancelled) return;
      setCheckJobFailed(status === "failed");
      setLaneJob(novelId, "check", null);
      setCheckJobId(null);
    })();
    return () => {
      cancelled = true;
    };
  }, [checkJobId, checkJob.data?.status, novelId]);

  /** The trigger's one contract: while the lane holds a job whose poll
   *  failed, the click RESUMES the poll — the job may still be running
   *  server-side, and a fresh enqueue would pile a second check onto it
   *  (nothing refuses it there) — unless the poll answered 404: the row
   *  itself is gone, no resume could ever answer, and the click clears
   *  the lane and enqueues fresh. A fresh enqueue also when the lane is
   *  idle or the job settled failed; a refused enqueue keeps the
   *  trigger live (the lane never heard of it — the retry is the same
   *  button again). */
  async function check(): Promise<void> {
    if (checkJobId !== null && checkJob.isError) {
      if (!jobGone(checkJob.error)) {
        void checkJob.refetch();
        return;
      }
      setLaneJob(novelId, "check", null);
      setCheckJobId(null);
    }
    setCheckJobFailed(false);
    try {
      const accepted = await enqueue.mutateAsync();
      adoptCheckJob(accepted.job_id);
    } catch {
      // The refusal's alert stands on the mutation's own error face.
    }
  }

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
  // The review decisions' per-row faces, the findings' own discipline.
  const acceptRows = useDecisionRows();
  const discardRows = useDecisionRows();

  /** Accept one proposal: the entity is born, and the relations the
   *  accept could not place are announced once, on the row's own settle. */
  async function acceptSuggestion(suggestionId: string): Promise<void> {
    acceptRows.begin(suggestionId);
    try {
      const accepted = await accept.mutateAsync(suggestionId);
      onAccepted(accepted);
      acceptRows.settle(suggestionId, true);
    } catch {
      acceptRows.settle(suggestionId, false);
    }
  }

  /** Discard one proposal: the standing note leaves with the decision,
   *  and the row's face settles on its own answer. */
  async function discardSuggestion(suggestionId: string): Promise<void> {
    setSkippedNote(null);
    discardRows.begin(suggestionId);
    try {
      await discard.mutateAsync(suggestionId);
      discardRows.settle(suggestionId, true);
    } catch {
      discardRows.settle(suggestionId, false);
    }
  }

  // The extraction lane — the check's own discipline, one job at a time
  // on its own lane, adopted from the session on mount like the check's:
  // the settle refetches the suggestion queue (the extraction's result IS
  // the proposals), never the entities (only an accept creates one).
  const [extractJobId, setExtractJobId] = useState<string | null>(() =>
    laneJob(novelId, "extract"),
  );
  const [extractJobFailed, setExtractJobFailed] = useState(false);
  const extractJob = useJobQuery(extractJobId);
  // The accept's skipped relations (D8): announced once, transient —
  // the next decision or extraction clears the note; nothing persists it.
  const [skippedNote, setSkippedNote] = useState<string | null>(null);

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
      setLaneJob(novelId, "extract", null);
      setExtractJobId(null);
    })();
    return () => {
      cancelled = true;
    };
  }, [extractJobId, extractJob.data?.status, novelId]);

  /** The extraction trigger's contract, the check's own: while the lane
   *  holds a job whose poll failed, the click resumes the poll — never a
   *  second enqueue over work the server may still be running — unless
   *  the poll answered 404 (the row itself is gone; the click clears the
   *  lane and enqueues fresh, the check's own 404 discipline). No
   *  chapter is a no-op (the trigger is not offered); a refused enqueue
   *  keeps the trigger live. */
  async function extract(): Promise<void> {
    if (extractJobId !== null && extractJob.isError) {
      if (!jobGone(extractJob.error)) {
        void extractJob.refetch();
        return;
      }
      setLaneJob(novelId, "extract", null);
      setExtractJobId(null);
    }
    if (chapterId === null) return;
    setExtractJobFailed(false);
    setSkippedNote(null);
    try {
      const accepted = await extractEnqueue.mutateAsync({ chapterId });
      setLaneJob(novelId, "extract", accepted.job_id);
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
              ackBusy={ackRows.pending.has(finding.id)}
              dismissBusy={dismissRows.pending.has(finding.id)}
              failed={ackRows.refused.has(finding.id) || dismissRows.refused.has(finding.id)}
              onAcknowledge={(findingId) => void acknowledgeFinding(findingId)}
              onDismiss={(findingId) => void dismissFinding(findingId)}
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
              // The chip is a label, not a door: its click target — the
              // dossier panel — is Task 3/5's surface. Until that route
              // exists the chip offers no affordance (no disabled
              // promise); Task 3/5 wires the chip to the dossier.
              <li
                key={entity.id}
                data-testid="knowledge-entity-chip"
                className="inline-flex items-center gap-1 rounded-full bg-surface-container-high px-2 py-0.5 text-[11px]"
              >
                <span className="text-muted">
                  <Icon name={entityTypeIcon(entity.type)} size={12} />
                </span>
                <span className="font-medium text-foreground">{entity.name}</span>
                <span className="text-[10px] text-muted">{entityTypeLabel(t, entity.type)}</span>
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
                acceptBusy={acceptRows.pending.has(suggestion.id)}
                discardBusy={discardRows.pending.has(suggestion.id)}
                failed={acceptRows.refused.has(suggestion.id) || discardRows.refused.has(suggestion.id)}
                onAccept={(suggestionId) => void acceptSuggestion(suggestionId)}
                onDiscard={(suggestionId) => void discardSuggestion(suggestionId)}
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
