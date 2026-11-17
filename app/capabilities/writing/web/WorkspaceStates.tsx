/**
 * The workspace's loading and error faces (W4 Task 11) — `workspace-states`
 * Kacheln 1 and 2 on the shell's tokens. The skeleton is the shell's quiet
 * pulse (the Bone family, the shelf's own discipline — the draft's moving
 * shimmer would need a keyframe the token surface does not carry; the calm
 * is the draft's own requirement).
 *
 * The error card carries the ROUND-2 CORRECTED copy verbatim (d8e51c9d,
 * PR #889 — the owner's #887 ruling: rework via Stitch, the browser-cache
 * reassurance and the „Offline-Kopie ansehen" door gone, the retry alone).
 * The body's autosave reassurance („Deine Änderungen bleiben im Editor,
 * bis sie gesichert sind.") becomes true with Task 12's autosave engine
 * (PR 3, this same wave, sequential): the coordinator ruled the verbatim
 * authority wins over a self-devised true-today body — a short, documented
 * interim, not a papered-over claim.
 *
 * The loading line stays „Manuskript wird geladen …": the round corrected
 * only the error tile, KACHEL 1 still draws „Manuskript-Index wird
 * synchronisiert …" — a sync-engine claim nothing implements (the #884
 * family), so the port keeps the honest loading verb.
 */

import { useTranslation } from "@shell/lib/i18n";
import { Icon } from "@shell/ui/icons";

import { Bone } from "./ShelfStates";

/** The shell's focus ring on the one control the error state offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

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
