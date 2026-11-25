/**
 * The interview's transcript (W9 Task 10): the opening question (chrome from
 * the catalog, not a turn), then every line the writer and the assistant
 * actually said, oldest first, each answer a status region. A pending
 * suggestion draws its own inset card with the three actions; a settled
 * acceptance keeps its «übernommen» mark. A named failure stands where the
 * answer would have been, names the reason and keeps the writer's text in
 * the composer beside it.
 */
import type { AssistantTurnRead } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { FOCUS } from "@shell/ui/card";
import { Icon } from "@shell/ui/icons";

import type { InterviewFailure } from "./interviewState";

function timeOf(createdAt: string): string {
  const date = new Date(createdAt);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function FailureFace({
  failure,
  busy,
  onRetry,
}: {
  failure: InterviewFailure;
  busy: boolean;
  onRetry: () => void;
}) {
  const t = useTranslation();
  const copy =
    failure.code === "extraction-failed"
      ? t("knowledge.interview.failedExtraction")
      : failure.code === "provider-unavailable"
        ? t("knowledge.interview.failedUnavailable")
        : failure.code === "prompt-refused"
          ? t("knowledge.interview.failedPrompt")
          : failure.code === "suggestion-mismatch"
            ? t("knowledge.interview.failure.suggestion-mismatch")
            : t("knowledge.interview.failedProvider");
  // A stale suggestion is settled by reading the current one, not by sending
  // the same body again; a refused prompt needs its editor.
  const canRetry = failure.code !== "prompt-refused" && failure.code !== "suggestion-mismatch";

  return (
    <div
      data-testid="entity-interview-failure"
      role="alert"
      className="flex flex-col gap-2 rounded border border-warning/40 bg-surface-container p-2.5"
    >
      <div className="flex items-start gap-2">
        <span className="mt-0.5 shrink-0 text-warning">
          <Icon name="warning" size={18} />
        </span>
        <div className="min-w-0">
          <p className="text-[11px] leading-snug text-foreground">{copy}</p>
          {failure.cause !== undefined && (
            <p className="mt-0.5 font-mono text-[10px] text-muted">{failure.cause}</p>
          )}
        </div>
      </div>
      <div className="flex flex-wrap justify-end gap-1.5">
        {failure.code === "provider-unavailable" && (
          <a
            href="/settings/ai-regeln"
            data-testid="entity-interview-settings-door"
            className={`rounded border border-rule bg-card px-2 py-1 text-[10px] text-primary transition-colors hover:bg-surface-container-low ${FOCUS}`}
          >
            {t("knowledge.interview.settingsDoor")}
          </a>
        )}
        {failure.code === "prompt-refused" && (
          <a
            href="/settings/prompts"
            data-testid="entity-interview-prompt-door"
            className={`rounded border border-rule bg-card px-2 py-1 text-[10px] text-primary transition-colors hover:bg-surface-container-low ${FOCUS}`}
          >
            {t("knowledge.interview.promptDoor")}
          </a>
        )}
        {canRetry && (
          <button
            type="button"
            data-testid="entity-interview-retry"
            disabled={busy}
            onClick={onRetry}
            className={`rounded border border-rule bg-card px-2 py-1 text-[10px] font-semibold text-primary transition-colors hover:bg-surface-container-low disabled:cursor-not-allowed disabled:text-muted ${FOCUS}`}
          >
            {t("knowledge.interview.retry")}
          </button>
        )}
      </div>
    </div>
  );
}

function SuggestionCard({
  turn,
  busy,
  onAccept,
  onEdit,
  onReject,
}: {
  turn: AssistantTurnRead;
  busy: boolean;
  onAccept: () => void;
  onEdit: () => void;
  onReject: () => void;
}) {
  const t = useTranslation();
  const pending = turn.suggestion_state === "pending";
  if (turn.suggestion === null || (!pending && turn.suggestion_state !== "accepted")) return null;
  return (
    <div
      data-testid={pending ? "entity-interview-suggestion" : undefined}
      className="mt-1 flex flex-col gap-2 rounded border border-primary/30 bg-card p-2.5 shadow-card"
    >
      <div className="flex items-center justify-between gap-1">
        <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-primary">
          <Icon name="spark" size={14} />
          {t("knowledge.interview.proposalTitle")}
        </span>
        {!pending && (
          <span className="flex items-center gap-1 text-[10px] text-success">
            <Icon name="check" size={13} />
            {t("knowledge.interview.accepted")}
          </span>
        )}
      </div>
      <p className="text-body leading-snug text-foreground">{turn.suggestion}</p>
      {pending && (
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            data-testid="entity-interview-suggestion-accept"
            disabled={busy}
            onClick={onAccept}
            className={`rounded bg-primary px-2 py-1 text-[10px] font-semibold text-primary-foreground transition-colors hover:opacity-95 disabled:cursor-not-allowed disabled:bg-surface-container disabled:text-muted ${FOCUS}`}
          >
            {t("knowledge.interview.accept")}
          </button>
          <button
            type="button"
            data-testid="entity-interview-suggestion-edit"
            disabled={busy}
            onClick={onEdit}
            className={`rounded border border-rule bg-card px-2 py-1 text-[10px] text-foreground transition-colors hover:bg-surface-container-low disabled:cursor-not-allowed disabled:text-muted ${FOCUS}`}
          >
            {t("knowledge.interview.edit")}
          </button>
          <button
            type="button"
            data-testid="entity-interview-suggestion-reject"
            disabled={busy}
            onClick={onReject}
            className={`px-1.5 py-1 text-[10px] text-muted transition-colors hover:text-danger disabled:cursor-not-allowed ${FOCUS}`}
          >
            {t("knowledge.interview.reject")}
          </button>
        </div>
      )}
    </div>
  );
}

export function Transcript({
  opening,
  turns,
  pending,
  failure,
  busy,
  onAccept,
  onEdit,
  onReject,
  onRetry,
}: {
  opening: string;
  turns: readonly AssistantTurnRead[];
  pending: boolean;
  failure: InterviewFailure | null;
  busy: boolean;
  onAccept: (turn: AssistantTurnRead) => void;
  onEdit: (turn: AssistantTurnRead) => void;
  onReject: () => void;
  onRetry: () => void;
}) {
  const t = useTranslation();

  return (
    <div
      data-testid="entity-interview-transcript"
      role="log"
      aria-label={t("knowledge.interview.transcriptAria")}
      tabIndex={0}
      className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto px-3 py-3"
    >
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] font-semibold text-primary">{t("knowledge.interview.assistant")}</span>
        </div>
        <div role="status" className="rounded border border-rule bg-surface-container-low p-2 text-body leading-relaxed text-foreground">
          {opening}
        </div>
      </div>

      {turns.map((turn) => {
        if (turn.role === "user") {
          return (
            <div key={turn.seq} className="flex flex-col items-end gap-1">
              <div className="flex items-center gap-1.5">
                <span className="text-[11px] font-semibold text-foreground">{t("knowledge.interview.you")}</span>
                <span className="text-[10px] text-muted">· {timeOf(turn.created_at)}</span>
              </div>
              <div className="max-w-[92%] rounded border border-primary/20 bg-secondary-container/30 p-2 text-body leading-relaxed text-foreground">
                {turn.text}
              </div>
            </div>
          );
        }
        return (
          <div key={turn.seq} className="flex flex-col gap-1">
            <div className="flex items-center gap-1.5">
              <span className="text-[11px] font-semibold text-primary">{t("knowledge.interview.assistant")}</span>
              <span className="text-[10px] text-muted">· {timeOf(turn.created_at)}</span>
            </div>
            <div
              role="status"
              className="rounded border border-rule bg-surface-container-low p-2 text-body leading-relaxed text-foreground"
            >
              {turn.text}
            </div>
            <SuggestionCard
              turn={turn}
              busy={busy}
              onAccept={() => onAccept(turn)}
              onEdit={() => onEdit(turn)}
              onReject={onReject}
            />
          </div>
        );
      })}

      {pending && (
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-1.5 text-primary">
            <span className="text-[11px] font-semibold">{t("knowledge.interview.assistant")}</span>
            <span aria-hidden="true" className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary/40" />
          </div>
          <div
            role="status"
            className="inline-flex items-center gap-2 rounded border border-rule bg-surface-container-low px-2.5 py-1.5 text-meta text-muted"
          >
            <span aria-hidden="true" className="h-3 w-3 animate-spin rounded-full border-2 border-primary/30 border-t-primary" />
            <span>{t("knowledge.interview.thinking")}</span>
          </div>
        </div>
      )}

      {failure !== null && <FailureFace failure={failure} busy={busy} onRetry={onRetry} />}
    </div>
  );
}
