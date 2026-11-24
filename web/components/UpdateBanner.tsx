/**
 * The shell's update surfaces: the persistent banner under the topbar, the
 * one-shot start toast, and the door into the release notes.
 *
 * The banner is the required surface (design 2026-11-24): it names the newer
 * release and stays until the reader defers it for this page load (Later) or
 * ignores the version for good (the dialog's answer, which posts the
 * dismissal and writes the server's answer into the cache). The start toast
 * is the transient notice — one per version per mount, eight seconds, then
 * gone; the banner remains. Nothing renders while the check is pending or
 * failed, or when no newer release exists: offline shows the last known
 * answer or nothing, never an error.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { client } from "../lib/api/client";
import { useTranslation } from "../lib/i18n";
import { UPDATE_KEY, useUpdateCheck, type UpdateRead } from "../lib/updates";
import { FOCUS } from "../ui/card";
import { ReleaseNotesDialog } from "./ReleaseNotesDialog";

/** How long the start notice stands before the page returns to the banner. */
const TOAST_MS = 8000;

/** The versions this page load already toasted. Module scope, not a ref: a
 *  banner remount is still the same page load, and the notice is per version
 *  per load (the SPA never reloads this module on navigation). */
const announced = new Set<string>();

/** Test-only: a fresh test module stands for a fresh page load. */
export function resetAnnouncedUpdates(): void {
  announced.clear();
}

export function UpdateBanner() {
  const t = useTranslation();
  const queryClient = useQueryClient();
  const update = useUpdateCheck();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deferred, setDeferred] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const notesButton = useRef<HTMLButtonElement | null>(null);

  const answer = update.data;
  const version =
    answer !== undefined && answer.update_available && !answer.dismissed
      ? answer.latest_version
      : null;
  const visible = version !== null && !deferred;

  useEffect(() => {
    if (version === null || announced.has(version)) return;
    announced.add(version);
    setToast(version);
    const id = window.setTimeout(() => setToast(null), TOAST_MS);
    return () => window.clearTimeout(id);
  }, [version]);

  async function dismissVersion(opened: UpdateRead): Promise<void> {
    try {
      const { data, response } = await client.POST("/api/updates/dismiss", {
        body: { version: opened.latest_version ?? opened.current_version },
      });
      if (response.ok && data !== undefined) {
        // The server's own answer hides the strip: update_available is false
        // for the dismissed version, and a later release announces again.
        queryClient.setQueryData(UPDATE_KEY, data);
      }
    } catch {
      // A refused dismissal stays silent: the strip is still there, and the
      // next check reconciles. The dialog closes either way.
    } finally {
      void queryClient.invalidateQueries({ queryKey: UPDATE_KEY });
      setToast(null);
      setDialogOpen(false);
    }
  }

  return (
    <>
      {visible ? (
        <div
          role="status"
          data-testid="update-banner"
          className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-surface-container-low px-4 py-2"
        >
          <p className="text-meta font-medium text-foreground">
            {t("shell.update.available", { version })}
          </p>
          <div className="flex shrink-0 items-center gap-2">
            <button
              ref={notesButton}
              type="button"
              onClick={() => setDialogOpen(true)}
              className={`rounded bg-primary px-3 py-1 text-meta font-medium text-primary-foreground transition-colors hover:opacity-90 ${FOCUS}`}
            >
              {t("shell.update.notes")}
            </button>
            <button
              type="button"
              onClick={() => setDeferred(true)}
              className={`rounded border border-border px-3 py-1 text-meta font-medium text-muted transition-colors hover:bg-surface-container-lowest hover:text-foreground ${FOCUS}`}
            >
              {t("shell.update.later")}
            </button>
          </div>
        </div>
      ) : null}

      {visible && toast !== null ? (
        <div
          role="status"
          aria-live="polite"
          data-testid="update-toast"
          className="fixed bottom-4 right-4 z-40 max-w-sm rounded-lg border border-border bg-surface-container-lowest px-4 py-3 text-body text-foreground shadow-overlay"
        >
          {t("shell.update.toast", { version: toast })}
        </div>
      ) : null}

      {dialogOpen && answer !== undefined ? (
        <ReleaseNotesDialog
          update={answer}
          onClose={() => setDialogOpen(false)}
          onDismiss={() => void dismissVersion(answer)}
          returnFocusTo={notesButton}
        />
      ) : null}
    </>
  );
}
