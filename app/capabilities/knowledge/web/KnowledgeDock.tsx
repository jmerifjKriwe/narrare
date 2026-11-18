/**
 * The knowledge dock face (W5 Task 1) — the workspace's dock registry
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
 * - The entity-chip area: INTERIM #867 — Task 2 fills it from the novel's
 *   entities; the spotlight geometry stands neutral until then.
 *
 * The draft's „Verifizierte Entitäten" list is mock data (no per-entity
 * consistency status exists on any model) — it ships as the neutral
 * placeholder, never as invented verified rows.
 */
import type { UseMutationResult } from "@tanstack/react-query";
import { useParams } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import type { Finding } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import {
  queryClient,
  useAcknowledgeFinding,
  useDismissFinding,
  useEnqueueCheck,
  useFindingsQuery,
  useJobQuery,
} from "@shell/lib/query";
import { Icon } from "@shell/ui/icons";

/** The shell's focus ring on every control the face offers. */
const FOCUS = "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The draft's card eyebrow — the micro-label above each card's content. */
const CARD_EYEBROW = "text-[10px] font-bold uppercase tracking-wider text-muted";

/** One neutral field row — the label left, the dash right, mono. */
function NeutralRow({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-between text-meta">
      <span className="text-muted">{label}</span>
      <span className="font-mono text-muted">—</span>
    </div>
  );
}

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

export function KnowledgeDock() {
  const t = useTranslation();
  // The novel is the workspace route's own param — the dock reads the
  // book it stands beside, never a parsed pathname.
  const { novelId } = useParams({ from: "/novels/$novelId" });
  const findings = useFindingsQuery(novelId);
  const enqueue = useEnqueueCheck(novelId);
  const acknowledge = useAcknowledgeFinding(novelId);
  const dismiss = useDismissFinding(novelId);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobFailed, setJobFailed] = useState(false);
  const job = useJobQuery(jobId);

  // The honest busy: the enqueue in flight, or a job outstanding whose
  // poll still answers. A dead poll cannot keep the promise of movement
  // — it unlocks the trigger and names itself instead.
  const pollFailed = job.isError;
  const busy = enqueue.isPending || (jobId !== null && !pollFailed);
  const checkFailed = enqueue.isError || jobFailed;

  // The settle beat: a done or failed row refetches the pending findings
  // (the check's result IS the queue), and only then does the busy face
  // lift — the count the writer reads next is the refetched truth. The
  // poll retires with the jobId; no timer outlives the answer.
  useEffect(() => {
    const status = job.data?.status;
    if (jobId === null || (status !== "done" && status !== "failed")) return;
    let cancelled = false;
    void (async () => {
      await queryClient.invalidateQueries({ queryKey: ["knowledge", "findings", novelId] });
      if (cancelled) return;
      setJobFailed(status === "failed");
      setJobId(null);
    })();
    return () => {
      cancelled = true;
    };
  }, [jobId, job.data?.status, novelId]);

  /** Enqueue the check and select its job for polling; a refused enqueue
   *  keeps the trigger live (the lane never heard of it — the retry is
   *  the same button again). */
  async function check() {
    setJobFailed(false);
    try {
      const accepted = await enqueue.mutateAsync();
      setJobId(accepted.job_id);
    } catch {
      // The refusal's alert stands on the mutation's own error face.
    }
  }

  const count = findings.data?.length ?? 0;

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
          disabled={busy}
          aria-busy={busy}
          className={`flex w-full items-center justify-center gap-1.5 rounded border border-border bg-surface-container-low px-2 py-1.5 text-meta font-medium text-foreground transition-colors hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-60 ${FOCUS}`}
        >
          <Icon name="refresh" size={13} />
          <span>{busy ? t("knowledge.dock.checkBusy") : t("knowledge.dock.check")}</span>
        </button>
        {checkFailed && (
          <p role="alert" className="text-meta text-danger">
            {t("knowledge.dock.checkFailed")}
          </p>
        )}
        {pollFailed && !checkFailed && (
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
        <div
          role="alert"
          className="space-y-1.5 rounded-lg border border-danger/40 bg-panel p-3 text-center"
        >
          <p className="text-meta text-danger">{t("knowledge.dock.loadFailed")}</p>
          <button
            type="button"
            onClick={() => void findings.refetch()}
            className={`rounded border border-border bg-surface-container-low px-2.5 py-1 text-[11px] font-medium text-foreground transition-colors hover:bg-surface-container ${FOCUS}`}
          >
            {t("knowledge.dock.retry")}
          </button>
        </div>
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

      {/* Entity chips — INTERIM #867: Task 2 fills this face from the
          novel's entities (the extraction's accepted rows). The
          spotlight geometry stands neutral until then — no invented
          entity, the wiki door disabled with its note. */}
      <div
        data-testid="knowledge-entity"
        className="space-y-2.5 rounded-lg border border-border bg-panel p-3 shadow-card"
      >
        <div className="flex items-center justify-between">
          <span className={CARD_EYEBROW}>{t("knowledge.dock.entity")}</span>
          <span className="font-mono text-muted">—</span>
        </div>
        <div className="space-y-1.5 py-1">
          <NeutralRow label={t("knowledge.dock.entityName")} />
          <NeutralRow label={t("knowledge.dock.entityFirst")} />
          <NeutralRow label={t("knowledge.dock.entityBinding")} />
        </div>
        <button
          type="button"
          disabled
          title={t("knowledge.dock.wikiNote")}
          className="flex w-full cursor-not-allowed items-center justify-center gap-1 rounded border border-border/70 bg-surface-container-low/60 px-2 py-1.5 text-[11px] font-medium text-muted opacity-60"
        >
          <Icon name="menuBook" size={12} />
          <span>{t("knowledge.dock.wiki")}</span>
        </button>
      </div>
    </div>
  );
}
