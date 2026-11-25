/**
 * The entity interview (W9 Task 10) — the graph page's right column while the
 * route's `interview` parameter stands. It owns the conversation and every
 * face the states reference draws: the type chooser (with «Von Hand anlegen»
 * as the quiet second path), the first question, the assistant thinking, the
 * answered proposal, a suggestion for one question, everything suggested, the
 * named failures, the ended interview and the list. The proposal card and the
 * transcript are separate faces of the same session; the footer offers
 * «Interview beenden» — the handover into the create dialog is its own task.
 *
 * The opening question is chrome from knowledge's catalog, one per type: it
 * is not a turn and costs no model call. The panel is a labelled complementary
 * region; hiding it (the header's close button) only leaves the URL, never
 * closes the session.
 */
import { useEffect, useId, useState } from "react";

import type { AssistantTurnRead } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { FOCUS } from "@shell/ui/card";
import { Icon } from "@shell/ui/icons";

import { entityTypeLabel } from "../entityTypes";
import { Composer } from "./Composer";
import { ProposalCard } from "./ProposalCard";
import { SessionList } from "./SessionList";
import { Transcript } from "./Transcript";
import { TypeChooser } from "./TypeChooser";
import { openingQuestionKey } from "./interviewState";
import { useInterview } from "./useInterview";

export function EntityInterview({
  novelId,
  sessionId,
  onSelectSession,
  onClose,
  onManual,
}: {
  novelId: string;
  /** The interview's id, or null for the chooser (the `new` door). */
  sessionId: string | null;
  /** A row of the list or a fresh `new`; the graph writes the URL. */
  onSelectSession: (target: string) => void;
  /** The header's close button: hide the panel, never close the session. */
  onClose: () => void;
  /** «Von Hand anlegen»: the existing create dialog, one call away. */
  onManual: () => void;
}) {
  const t = useTranslation();
  const titleId = useId();
  const controller = useInterview({
    novelId,
    sessionId,
    onOpened: onSelectSession,
    onNotFound: () => onSelectSession("new"),
  });
  const [listOpen, setListOpen] = useState(false);
  const [expanded, setExpanded] = useState(true);

  // A session switch is a new conversation: the list closes and the proposal
  // stands open, as it does on a fresh arrival.
  // biome-ignore lint/correctness/useExhaustiveDependencies: sessionId is the deliberate reset trigger; the body only resets local view state.
  useEffect(() => {
    setListOpen(false);
    setExpanded(true);
  }, [sessionId]);

  const session = controller.session;
  const typeLabel = entityTypeLabel(t, session?.entity_type ?? "generic");
  const busy = controller.face === "thinking" || controller.ending;

  function accept(turn: AssistantTurnRead) {
    if (turn.suggestion === null) return;
    // The server stores the pending suggestion's own text; the client sends
    // only the act, and the empty text is the wire's one licensed empty.
    controller.send({ text: "", act: "accept-suggestion" });
  }

  return (
    <aside
      data-testid="entity-interview"
      role="complementary"
      aria-labelledby={titleId}
      className="absolute inset-0 z-20 flex min-h-0 w-full flex-col overflow-hidden border-l border-rule bg-panel lg:static lg:w-[380px] lg:shrink-0"
    >
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-rule bg-surface-container-low px-3 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <h2 id={titleId} className="truncate text-label font-semibold text-foreground">
            {t("knowledge.interview.title")}
          </h2>
          {session !== null && (
            <span className="inline-flex shrink-0 items-center gap-1 rounded bg-surface-container px-1.5 py-0.5 text-[11px] text-primary">
              <Icon name="archive" size={13} />
              {typeLabel}
            </span>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1 text-muted">
          <button
            type="button"
            data-testid="entity-interview-sessions"
            aria-label={t("knowledge.interview.listAria")}
            aria-pressed={listOpen}
            title={t("knowledge.interview.listAria")}
            onClick={() => setListOpen((open) => !open)}
            className={`flex h-6 w-6 items-center justify-center rounded transition-colors hover:bg-surface-container hover:text-foreground ${FOCUS}`}
          >
            <Icon name="viewList" size={16} />
          </button>
          <button
            type="button"
            data-testid="entity-interview-close"
            aria-label={t("knowledge.interview.close")}
            title={t("knowledge.interview.close")}
            onClick={onClose}
            className={`flex h-6 w-6 items-center justify-center rounded transition-colors hover:bg-surface-container hover:text-foreground ${FOCUS}`}
          >
            <Icon name="cross" size={16} />
          </button>
        </div>
      </div>

      {listOpen ? (
        <SessionList
          sessions={controller.sessions}
          onOpen={(id) => onSelectSession(id)}
          onNew={() => onSelectSession("new")}
          onClose={() => setListOpen(false)}
        />
      ) : sessionId === null ? (
        <TypeChooser
          onStart={controller.start}
          onManual={onManual}
          starting={controller.opening}
          startFailed={controller.startFailed}
        />
      ) : controller.reading ? (
        <div className="flex min-h-0 flex-1 items-center justify-center px-4">
          <p role="status" className="text-meta text-muted">
            {t("knowledge.interview.loading")}
          </p>
        </div>
      ) : controller.readFailed || session === null ? (
        <div className="flex min-h-0 flex-1 items-center justify-center p-4">
          <div role="alert" className="space-y-2 rounded border border-danger/40 bg-panel p-4 text-center">
            <p className="text-meta text-danger">{t("knowledge.interview.readFailed")}</p>
            <button
              type="button"
              onClick={controller.retryRead}
              className={`rounded border border-border bg-surface-container-low px-3 py-1.5 text-meta font-medium text-foreground transition-colors hover:bg-surface-container ${FOCUS}`}
            >
              {t("knowledge.interview.retry")}
            </button>
          </div>
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col">
          {controller.face === "ended" && (
            <div className="mx-3 mt-3 flex shrink-0 items-center gap-2 rounded border border-rule bg-surface-container-low px-2.5 py-1.5">
              <span className="text-muted">
                <Icon name="lock" size={15} />
              </span>
              <span className="text-[11px] text-muted">{t("knowledge.interview.endedBanner")}</span>
            </div>
          )}

          <ProposalCard
            proposal={session.proposal}
            typeLabel={typeLabel}
            expanded={expanded}
            onToggle={() => setExpanded((open) => !open)}
            dropping={busy}
            onDropSuggestions={() =>
              controller.send({ text: t("knowledge.interview.dropSuggestions"), act: "drop-suggestions" })
            }
          />

          <Transcript
            opening={t(openingQuestionKey(session.entity_type))}
            turns={session.turns}
            pending={controller.face === "thinking"}
            failure={controller.face === "failed" ? controller.failure : null}
            busy={busy}
            onAccept={accept}
            onEdit={(turn) => controller.setText(turn.suggestion ?? "")}
            onReject={() =>
              controller.send({ text: t("knowledge.interview.reject"), act: "reject-suggestion" })
            }
            onRetry={controller.retry}
          />

          {controller.face !== "ended" ? (
            <Composer
              text={controller.text}
              onChange={controller.setText}
              onSend={controller.sendText}
              onNoIdea={() => controller.send({ text: t("knowledge.interview.noIdea"), act: "no-idea" })}
              onFillAll={() => controller.send({ text: t("knowledge.interview.fillAll"), act: "fill-all" })}
              disabled={busy}
            />
          ) : (
            <div className="shrink-0 border-t border-rule px-3 py-2">
              <button
                type="button"
                onClick={() => onSelectSession("new")}
                className={`h-7 w-full rounded-[var(--radius-control)] border border-rule bg-card text-label text-primary transition-colors hover:bg-surface-container-low ${FOCUS}`}
              >
                {t("knowledge.interview.newInterview")}
              </button>
            </div>
          )}

          {controller.face !== "ended" && (
            <div className="shrink-0 border-t border-rule px-3 py-2">
              <button
                type="button"
                data-testid="entity-interview-end"
                disabled={busy}
                onClick={controller.end}
                className={`h-7 w-full rounded-[var(--radius-control)] border border-rule bg-card text-label text-muted transition-colors hover:text-foreground disabled:cursor-not-allowed disabled:opacity-60 ${FOCUS}`}
              >
                {t("knowledge.interview.endInterview")}
              </button>
            </div>
          )}
        </div>
      )}
    </aside>
  );
}
