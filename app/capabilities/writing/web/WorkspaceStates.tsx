/**
 * The workspace's state faces — `workspace-states` Kacheln 1 and 2 (W4 Task
 * 11) and the Kachel 10 leave guard (Task 12) on the shell's tokens. The
 * skeleton is the shell's quiet
 * pulse (the Bone family, the shelf's own discipline — the draft's moving
 * shimmer would need a keyframe the token surface does not carry; the calm
 * is the draft's own requirement).
 *
 * The error card carries the ROUND-2 CORRECTED copy verbatim (d8e51c9d,
 * PR #889 — the owner's #887 ruling: rework via Stitch, the browser-cache
 * reassurance and the „Offline-Kopie ansehen" door gone, the retry alone).
 * The body's autosave reassurance („Deine Änderungen bleiben im Editor,
 * bis sie gesichert sind.") is TRUE from Task 12: the autosave engine keeps
 * a refused body in memory until a retry lands it, so the words really do
 * stay in the editor. The coordinator's verbatim-authority ruling stands;
 * the short interim it named ended when the engine shipped (this PR).
 *
 * The loading line stays „Manuskript wird geladen …": the round corrected
 * only the error tile, KACHEL 1 still draws „Manuskript-Index wird
 * synchronisiert …" — a sync-engine claim nothing implements (the #884
 * family), so the port keeps the honest loading verb.
 */

import { useEffect, useId, useRef } from "react";

import { useTranslation } from "@shell/lib/i18n";
import { Icon } from "@shell/ui/icons";

import { Bone } from "./ShelfStates";

/** The shell's focus ring on the one control the error state offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The trap's population: every live control inside the panel, in DOM order. */
const FOCUSABLE =
  'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])';

/** Kachel 1 — the skeleton at the page's own geometry: the ribbon, the
 *  explorer strips, the editor card. Layout-stable, no flicker. */
export function WorkspaceLoading() {
  const t = useTranslation();
  return (
    <div role="status" className="flex h-full flex-col gap-3 p-4">
      <h1 className="sr-only">{t("writing.workspace.pageTitle")}</h1>
      {/* The ribbon's placeholder — half-transparent, the draft's opacity. */}
      <div className="flex items-center justify-between rounded border border-border/80 bg-panel/60 px-3 py-2 opacity-60">
        <div className="flex items-center gap-2">
          <Bone className="h-3 w-3 rounded-full" />
          <Bone className="h-2.5 w-24" />
        </div>
        <div className="flex items-center gap-2">
          <Bone className="h-2 w-16" />
          <Bone className="h-4 w-12" />
        </div>
      </div>
      <div className="grid flex-1 grid-cols-12 gap-3">
        {/* The explorer's strips. */}
        <div className="col-span-4 space-y-2.5 rounded border border-border bg-panel p-3">
          <Bone className="mb-2 h-2 w-14" />
          <div className="space-y-1.5">
            <Bone className="h-3 w-full" />
            <Bone className="h-2.5 w-4/5" />
            <Bone className="h-2.5 w-3/5" />
          </div>
          <div className="space-y-1.5 border-t border-border/60 pt-2">
            <Bone className="h-3 w-full" />
            <Bone className="h-2.5 w-3/4" />
          </div>
        </div>
        {/* The editor card's shimmer surface. */}
        <div className="col-span-8 flex flex-col justify-between rounded border border-border bg-panel p-4">
          <div className="space-y-2.5">
            <Bone className="h-2 w-20" />
            <Bone className="h-5 w-2/3" />
            <div className="space-y-1.5 pt-2">
              <Bone className="h-2 w-full" />
              <Bone className="h-2 w-11/12" />
              <Bone className="h-2 w-4/5" />
            </div>
          </div>
          <div className="mt-4 flex items-center gap-1.5 border-t border-border/40 pt-3 text-[11px] text-muted">
            <span aria-hidden="true" className="h-1.5 w-1.5 animate-pulse rounded-full bg-warning" />
            <span>{t("writing.workspace.loading")}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

/** Kachel 2 — the error card: the real failure, the honest cause, a retry
 *  that actually asks again. No offline-copy door (#887). */
export function WorkspaceError({
  message,
  retrying,
  onRetry,
}: {
  message: string;
  retrying: boolean;
  onRetry: () => void;
}) {
  const t = useTranslation();
  return (
    <div role="alert" className="flex h-full items-center justify-center p-6">
      <div className="w-full max-w-sm space-y-3 rounded-md border border-danger/30 bg-danger/5 p-5 text-center shadow-card">
        <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full border border-danger/30 bg-panel text-danger">
          <Icon name="warning" size={20} />
        </div>
        <div>
          <h1 className="text-body font-semibold text-danger">{t("writing.workspace.error.title")}</h1>
          <p className="mt-1 text-meta leading-relaxed text-muted">{t("writing.workspace.error.body")}</p>
          {/* The real failure — the query's own message, status included. */}
          <p className="mt-1 font-mono text-[11px] text-danger">{message}</p>
        </div>
        <div className="flex items-center justify-center pt-1">
          <button
            type="button"
            onClick={onRetry}
            disabled={retrying}
            className={`flex items-center gap-1.5 rounded bg-primary px-3.5 py-1.5 text-meta font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 active:scale-[0.98] ${FOCUS} ${retrying ? "cursor-not-allowed opacity-50" : ""}`}
          >
            <Icon name="refresh" size={14} />
            {retrying ? t("writing.shelf.error.retrying") : t("writing.shelf.error.retry")}
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Kachel 10 — the Abschiedsschutz (W4 Task 12): the leave guard the page
 * raises only after a write actually failed (a healthy pending body is
 * flushed first, never questioned — the WP0b rule). A calm modal over the
 * scrimmed editor, the draft's own geometry: the amber warning mark, the
 * serif question, the honest body, and the two answers. „Bleiben" is the
 * safe default — focus lands on it and Escape stays; „Verwerfen und
 * verlassen" carries the consequence on the control itself (the draft's
 * title), the honest second step before the words are dropped.
 *
 * Semantics at modal weight, the NewBookDialog discipline: role="alertdialog"
 * + aria-modal, labelled by its heading and described by its body, Tab wraps
 * inside the panel, the page behind the scrim held still. The page owns the
 * two outcomes — stay (reset the leave) or discard (drop the draft, then go);
 * both return focus to the control that raised the guard.
 */
export function LeaveGuardDialog({
  onStay,
  onDiscard,
}: {
  onStay: () => void;
  onDiscard: () => void;
}) {
  const t = useTranslation();
  const panelRef = useRef<HTMLDivElement | null>(null);
  const stayRef = useRef<HTMLButtonElement | null>(null);
  const headingId = useId();
  const bodyId = useId();

  // Opening lands focus on the safe answer and holds the page still; both
  // leave with the dialog — and closing returns focus to the control that
  // raised the guard (the TreeDialogs' focus-return discipline): a keyboard
  // writer is never stranded on <body> mid-crisis. A control the leave
  // itself retired is simply not focused — focus() on a detached node is a
  // no-op, the shelf's own rule.
  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    stayRef.current?.focus();
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
      opener?.focus();
    };
  }, []);

  // Escape stays — never discards by accident — and Tab wraps inside the
  // panel at both ends, the modal weight of the popover's keyboard discipline.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onStay();
        return;
      }
      if (event.key !== "Tab") return;
      const panel = panelRef.current;
      if (panel === null) return;
      const nodes = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (nodes.length === 0) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      const active = document.activeElement;
      if (event.shiftKey) {
        if (active === first || !panel.contains(active)) {
          event.preventDefault();
          last.focus();
        }
      } else if (active === last || !panel.contains(active)) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onStay]);

  return (
    // The scrim: the token's own 40% pair over the editor, the draft's soft
    // blur. The guard is deliberate — a press on the scrim does NOT discard;
    // only the two named answers leave (the draft's calm, no accidental loss).
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-scrim p-4 backdrop-blur-[1px]">
      <div
        ref={panelRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={headingId}
        aria-describedby={bodyId}
        className="w-full max-w-xs space-y-2.5 rounded-lg border border-border bg-panel p-4 text-center shadow-overlay"
      >
        <div className="mx-auto flex h-8 w-8 items-center justify-center rounded-full border border-warning/30 bg-warning/10 text-warning">
          <Icon name="warning" size={17} />
        </div>
        <div>
          <h2 id={headingId} className={`${SERIF} text-body font-semibold text-foreground`}>
            {t("writing.workspace.guard.title")}
          </h2>
          <p id={bodyId} className="mt-0.5 text-meta leading-snug text-muted">
            {t("writing.workspace.guard.body")}
          </p>
        </div>
        <div className="flex items-center justify-center gap-2 pt-1">
          <button
            type="button"
            ref={stayRef}
            onClick={onStay}
            className={`rounded bg-primary px-3 py-1.5 text-meta font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS}`}
          >
            {t("writing.workspace.guard.stay")}
          </button>
          <button
            type="button"
            onClick={onDiscard}
            title={t("writing.workspace.guard.discardNote")}
            className={`rounded border border-danger/40 px-2.5 py-1.5 text-meta font-medium text-danger transition-colors hover:bg-danger/10 ${FOCUS}`}
          >
            {t("writing.workspace.guard.discard")}
          </button>
        </div>
      </div>
    </div>
  );
}
