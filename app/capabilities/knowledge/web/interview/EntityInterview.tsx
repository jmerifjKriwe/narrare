/**
 * The entity interview (W9 Task 10) — the graph page's right column while the
 * route's `interview` parameter stands. The host owns the conversation and
 * every face the states reference draws: the type chooser (with «Von Hand
 * anlegen» as the quiet second path), the first question, the assistant
 * thinking, the answered proposal, a suggestion for one question, everything
 * suggested, the named failures, the ended interview and the list. The
 * proposal card and the transcript are separate faces of the same session; the
 * footer offers «Interview beenden» and «Als Entität speichern», which hands
 * the proposal to the create dialog as its prefill.
 *
 * The opening question is chrome from knowledge's catalog, one per type: it
 * is not a turn and costs no model call. The panel is a labelled complementary
 * region; hiding it (the header's close button) only leaves the URL, never
 * closes the session — which is why the host outlives the view: hiding must
 * not throw the conversation away.
 */
import { useCallback, useEffect, useId, useState } from "react";

import type { AssistantTurnRead } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { FOCUS } from "@shell/ui/card";
import { Icon } from "@shell/ui/icons";

import { entityTypeLabel } from "../entityTypes";
import { entityPrefillFromProposal, type EntityPrefill } from "../entityCreate";
import { Composer } from "./Composer";
import { ProposalCard } from "./ProposalCard";
import { SessionList } from "./SessionList";
import { Transcript } from "./Transcript";
import { TypeChooser } from "./TypeChooser";
import { openingQuestionKey, readyToSave } from "./interviewState";
import { useInterview } from "./useInterview";

type InterviewController = ReturnType<typeof useInterview>;

/**
 * The host the graph page renders for as long as the page stands. It owns the
 * conversation's state — the controller — so hiding the panel (dropping the
 * `interview` parameter) never resets a running turn, a failure or an unsent
 * draft. `undefined` hides it, `null` shows the chooser; the host remembers
 * the last session id it was shown so the read keeps following the turn while
 * the panel is away.
 */
export function EntityInterview({
  novelId,
  sessionId,
  onSelectSession,
  onClose,
  onManual,
  onSave,
  returnFocusId,
  closeFailed = false,
}: {
  novelId: string;
  /** The interview's id, null for the chooser (the `new` door), or undefined
   *  while the page hides the panel. */
  sessionId: string | null | undefined;
  /** A row of the list or a fresh `new`; the graph writes the URL. */
  onSelectSession: (target: string) => void;
  /** The header's close button: hide the panel, never close the session. */
  onClose: () => void;
  /** «Von Hand anlegen»: the existing create dialog, one call away. */
  onManual: () => void;
  /** «Als Entität speichern»: the proposal becomes the create dialog's prefill. */
  onSave: (prefill: EntityPrefill) => void;
  /** The door that opened the panel; closing it hands focus back there (the
   *  dialog opener contract — the panel's own close button unmounts with it). */
  returnFocusId?: string;
  /** A close fired by the handover (the save) failed after the row landed:
   *  the panel stays and names the failed end beside its own action. */
  closeFailed?: boolean;
}) {
  const hidden = sessionId === undefined;
  const [lastSessionId, setLastSessionId] = useState<string | null>(sessionId ?? null);

  // Hiding is not a session switch: the host keeps feeding the last id, so
  // the session read stays subscribed and the controller keeps selecting that
  // interview's slot while its turn settles.
  useEffect(() => {
    if (sessionId !== undefined) setLastSessionId(sessionId);
  }, [sessionId]);

  const onNotFound = useCallback(() => onSelectSession("new"), [onSelectSession]);
  const controller = useInterview({
    novelId,
    sessionId: hidden ? lastSessionId : sessionId,
    visible: !hidden,
    onOpened: onSelectSession,
    onNotFound,
  });

  if (hidden) return null;
  return (
    <EntityInterviewView
      sessionId={sessionId}
      controller={controller}
      onSelectSession={onSelectSession}
      onClose={onClose}
      onManual={onManual}
      onSave={onSave}
      returnFocusId={returnFocusId}
      closeFailed={closeFailed}
    />
  );
}

/** Everything the writer sees; it unmounts with the `interview` parameter and
 *  takes the host's controller as its prop. */
function EntityInterviewView({
  sessionId,
  controller,
  onSelectSession,
  onClose,
  onManual,
  onSave,
  returnFocusId,
  closeFailed,
}: {
  sessionId: string | null;
  controller: InterviewController;
  onSelectSession: (target: string) => void;
  onClose: () => void;
  onManual: () => void;
  onSave: (prefill: EntityPrefill) => void;
  returnFocusId?: string;
  closeFailed: boolean;
}) {
  const t = useTranslation();
  const titleId = useId();
  const [listOpen, setListOpen] = useState(false);
  const [expanded, setExpanded] = useState(true);

  // A session switch is a new conversation: the list closes and the proposal
  // stands open, as it does on a fresh arrival.
  // biome-ignore lint/correctness/useExhaustiveDependencies: sessionId is the deliberate reset trigger; the body only resets local view state.
  useEffect(() => {
    setListOpen(false);
    setExpanded(true);
  }, [sessionId]);

  // Closing the panel unmounts the button that had focus; the house pattern
  // hands it back to the opener rather than letting it fall to the body.
  useEffect(() => {
    if (returnFocusId === undefined) return;
    const id = returnFocusId;
    return () => document.getElementById(id)?.focus();
  }, [returnFocusId]);

  const session = controller.session;
  const typeLabel = entityTypeLabel(t, session?.entity_type ?? "generic");
  const busy = controller.face === "thinking" || controller.ending;
  // The ended face is read-only where the transcript writes: a suggestion's
  // three actions and the proposal's discard would get a silent
  // `session-closed` refusal or edit a composer that is not rendered. The
  // save door and «Neues Interview» stay live, so they read `busy` alone.
  const readOnly = controller.face === "ended";
  const canSave = session !== null && readyToSave(session.proposal);
  // A handover that created the entity but could not end the interview has
  // already spent this proposal: while that failure stands the save door is
  // shut, so a second press cannot create the same row again. Ending the
  // interview reaches the ended face, where the design lets it stay savable.
  const saveDoorShut = closeFailed && controller.face !== "ended";

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
          pending={controller.sessionsPending}
          onOpen={(id) => {
            // The list closes in the act itself: opening the session that
            // already stands writes the same parameter, so the session-change
            // effect below would not fire.
            setListOpen(false);
            onSelectSession(id);
          }}
          onNew={() => {
            setListOpen(false);
            onSelectSession("new");
          }}
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
            dropping={busy || readOnly}
            onDropSuggestions={() =>
              controller.send({ text: t("knowledge.interview.dropSuggestions"), act: "drop-suggestions" })
            }
          />

          <Transcript
            opening={t(openingQuestionKey(session.entity_type))}
            turns={session.turns}
            pending={controller.face === "thinking"}
            failure={controller.face === "failed" ? controller.failure : null}
            busy={busy || readOnly}
            onAccept={accept}
            onEdit={(turn) => controller.setText(turn.suggestion ?? "")}
            onReject={() =>
              controller.send({ text: t("knowledge.interview.reject"), act: "reject-suggestion" })
            }
            onRetry={controller.retry}
          />

          {controller.face !== "ended" && (
            <Composer
              text={controller.text}
              onChange={controller.setText}
              onSend={controller.sendText}
              onNoIdea={() => controller.send({ text: t("knowledge.interview.noIdea"), act: "no-idea" })}
              onFillAll={() => controller.send({ text: t("knowledge.interview.fillAll"), act: "fill-all" })}
              disabled={busy}
            />
          )}

          <div className="shrink-0 border-t border-rule px-3 py-2">
            {controller.face !== "ended" && (controller.endFailed || closeFailed) && (
              <p role="alert" className="mb-1.5 text-meta text-danger">
                {t("knowledge.interview.endFailed")}
              </p>
            )}
            <div className="flex items-center gap-2">
              <button
                type="button"
                id="entity-interview-save"
                data-testid="entity-interview-save"
                disabled={!canSave || busy || saveDoorShut}
                onClick={() =>
                  onSave(entityPrefillFromProposal(session.proposal, session.entity_type))
                }
                className={`h-7 flex-1 rounded-[var(--radius-control)] bg-primary text-label font-medium text-primary-foreground shadow-sm transition-colors hover:opacity-95 disabled:cursor-not-allowed disabled:bg-surface-container disabled:text-muted ${FOCUS}`}
              >
                {t("knowledge.interview.saveAsEntity")}
              </button>
              {controller.face === "ended" ? (
                <button
                  type="button"
                  data-testid="entity-interview-new"
                  onClick={() => onSelectSession("new")}
                  className={`h-7 shrink-0 rounded-[var(--radius-control)] border border-rule bg-card px-2 text-label text-primary transition-colors hover:bg-surface-container-low ${FOCUS}`}
                >
                  {t("knowledge.interview.newInterview")}
                </button>
              ) : (
                <button
                  type="button"
                  data-testid="entity-interview-end"
                  disabled={busy}
                  onClick={controller.end}
                  className={`h-7 shrink-0 rounded-[var(--radius-control)] border border-rule bg-card px-2 text-label text-muted transition-colors hover:text-foreground disabled:cursor-not-allowed disabled:opacity-60 ${FOCUS}`}
                >
                  {t("knowledge.interview.endInterview")}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
