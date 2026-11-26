/**
 * The interview's list (W9 Task 10): every session of the novel, the open
 * ones first and the ended ones after, each group in the server's order
 * (newest first). A row names the draft or says «noch ohne Name», shows its
 * type and state, and opens that interview — «Fortsetzen» while it is open,
 * «Ansehen» once it has ended. «Neues Interview» starts a fresh type choice.
 * While the read is still out the list draws its loading line alone, and a
 * read that failed with nothing cached draws its own sentence with «Erneut
 * versuchen» — neither a count nor a row claims a fact the wire has not
 * answered. A failed background refresh is not that face: the rows already
 * read stay, since a stale list beats an empty one.
 */
import type { AssistantSessionSummary } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { FOCUS } from "@shell/ui/card";
import { Icon } from "@shell/ui/icons";

import { entityTypeLabel } from "../entityTypes";

function SessionRow({
  session,
  onOpen,
}: {
  session: AssistantSessionSummary;
  onOpen: (id: string) => void;
}) {
  const t = useTranslation();
  const open = session.closed_at === null;
  return (
    <div className="flex items-center justify-between gap-2 rounded border border-rule bg-card p-2.5 transition-colors hover:border-primary/40">
      <div className="flex min-w-0 flex-col">
        <span className={`truncate text-label ${open ? "font-semibold text-foreground" : "text-foreground"}`}>
          {session.name !== null && session.name.trim() !== "" ? session.name : (
            <span className="italic text-muted">{t("knowledge.interview.noName")}</span>
          )}
        </span>
        <span className="flex items-center gap-1.5 text-[10px] text-muted">
          <span>{entityTypeLabel(t, session.entity_type ?? "generic")}</span>
          <span aria-hidden="true">·</span>
          <span className={open ? "text-warning" : undefined}>
            {open ? t("knowledge.interview.openState") : t("knowledge.interview.closedState")}
          </span>
        </span>
      </div>
      <button
        type="button"
        onClick={() => onOpen(session.id)}
        className={`shrink-0 text-[11px] font-semibold text-primary hover:underline ${FOCUS}`}
      >
        {open ? t("knowledge.interview.resume") : t("knowledge.interview.view")}
      </button>
    </div>
  );
}

export function SessionList({
  sessions,
  pending,
  failed,
  onOpen,
  onNew,
  onClose,
  onRetry,
}: {
  sessions: readonly AssistantSessionSummary[];
  /** The list's read is still out: the list says so instead of counting a
   *  zero and drawing no row, which would state a fact the wire has not. */
  pending: boolean;
  /** The list's read failed and no row is cached: its own sentence and the
   *  retry stand instead of the zero and the rows the wire never answered. */
  failed: boolean;
  onOpen: (id: string) => void;
  onNew: () => void;
  onClose: () => void;
  /** Asks the list's read again. */
  onRetry: () => void;
}) {
  const t = useTranslation();
  const open = sessions.filter((session) => session.closed_at === null);
  const closed = sessions.filter((session) => session.closed_at !== null);

  return (
    <div data-testid="entity-interview-list" className="flex min-h-0 flex-1 flex-col overflow-y-auto px-3 py-3">
      <div className="-mx-3 -mt-3 mb-3 flex items-center justify-between border-b border-rule px-3 py-2">
        <span className="flex items-center gap-2 text-label font-semibold text-foreground">
          {t("knowledge.interview.listTitle")}
          <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-primary" />
        </span>
        <button
          type="button"
          aria-label={t("knowledge.interview.close")}
          onClick={onClose}
          className={`flex h-6 w-6 items-center justify-center rounded text-muted transition-colors hover:bg-surface-container-low hover:text-foreground ${FOCUS}`}
        >
          <Icon name="cross" size={15} />
        </button>
      </div>
      <button
        type="button"
        onClick={onNew}
        className={`mb-4 flex h-8 w-full items-center justify-center gap-1.5 rounded-[var(--radius-control)] bg-primary text-label font-semibold text-primary-foreground shadow-card transition-colors hover:opacity-95 ${FOCUS}`}
      >
        <Icon name="plus" size={15} />
        {t("knowledge.interview.newInterview")}
      </button>

      {pending ? (
        <p
          role="status"
          data-testid="entity-interview-list-loading"
          className="px-1 text-meta text-muted"
        >
          {t("knowledge.interview.listLoading")}
        </p>
      ) : failed ? (
        <div
          data-testid="entity-interview-list-failed"
          className="rounded border border-danger/40 bg-panel p-3 text-center"
        >
          <p role="alert" className="text-meta text-danger">
            {t("knowledge.interview.listFailed")}
          </p>
          <button
            type="button"
            onClick={onRetry}
            className={`mt-2 rounded border border-border bg-surface-container-low px-3 py-1.5 text-meta font-medium text-foreground transition-colors hover:bg-surface-container ${FOCUS}`}
          >
            {t("knowledge.interview.retry")}
          </button>
        </div>
      ) : (
        <>
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between px-1">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted">
                {t("knowledge.interview.openTitle")}
              </span>
              <span className="font-mono text-[10px] text-primary">
                {t("knowledge.interview.sessionsCount", { count: open.length })}
              </span>
            </div>
            {open.map((session) => (
              <SessionRow key={session.id} session={session} onOpen={onOpen} />
            ))}
          </div>

          {closed.length > 0 && (
            <div className="mt-4 flex flex-col gap-1.5">
              <div className="flex items-center justify-between px-1">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-muted">
                  {t("knowledge.interview.closedTitle")}
                </span>
                <span className="font-mono text-[10px] text-muted">
                  {t("knowledge.interview.closedCount", { count: closed.length })}
                </span>
              </div>
              {closed.map((session) => (
                <SessionRow key={session.id} session={session} onOpen={onOpen} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
