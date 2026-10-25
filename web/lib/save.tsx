import { useCallback, useEffect, useRef, useState } from "react";

import { client } from "./api/client";
import { useTranslation } from "./i18n";

export type SaveStatus = "idle" | "pending" | "saving" | "saved" | "failed";
/** `stale` is an answer addressed to an attempt that is no longer the page's:
 *  the body was discarded or the hook went away. It is neither a save nor a
 *  failure to ask the user about. */
export type FlushOutcome = "clean" | "saved" | "failed" | "stale";

const DELAY_MS = 800;

/**
 * Whether a status means text that exists only in the browser: waiting for
 * its debounce, on the wire, or refused. The page's guards (leave, the
 * router blocker, the browser's own unload prompt) all ask this one question,
 * so a fourth caller cannot answer it differently.
 */
export function unsavedStatus(status: SaveStatus): boolean {
  return status !== "idle" && status !== "saved";
}

/**
 * Debounced save that tells the truth about the answer: a refused or failed
 * write is `failed` — named beside the text — and the body it carried stays
 * in memory, so the next keystroke retries it. Success, and only success, is
 * `saved`. The endpoint is idempotent, so a duplicate flush costs nothing.
 *
 * Writes are serialized: a flush that arrives while one is on the wire waits
 * for it and then carries the latest body. Two overlapping PUTs could answer
 * out of order and let the older body win both the page's cache and the
 * server row; one at a time cannot.
 */
export function useAutosave(
  chapterId: string | null,
  onSaved?: (chapterId: string, body: string) => void,
) {
  const [status, setStatus] = useState<SaveStatus>("idle");
  const timer = useRef<number | null>(null);
  const pending = useRef<string | null>(null);
  const id = useRef(chapterId);
  id.current = chapterId;
  const saved = useRef(onSaved);
  saved.current = onSaved;
  // Bumped when the hook goes away or the body is dropped: an answer that
  // lands after that belongs to an attempt nobody is waiting for.
  const generation = useRef(0);
  // The tail of the write queue. Never rejects: `attempt` resolves every path.
  const writes = useRef<Promise<FlushOutcome>>(Promise.resolve("clean"));

  const attempt = useCallback(async (): Promise<FlushOutcome> => {
    const body = pending.current;
    const target = id.current;
    if (body === null || target === null) return "clean";
    // The body stays in `pending` until the answer: dropping it here is what
    // made a refused write unrecoverable. A body typed while this request is
    // in flight replaces it there and must survive the answer.
    const attemptGeneration = generation.current;
    setStatus("saving");
    try {
      const { error, response } = await client.PUT(
        "/api/writing/chapters/{chapter_id}",
        { params: { path: { chapter_id: target } }, body: { body } },
      );
      if (attemptGeneration !== generation.current) return "stale";
      // `error` is the parsed error body; a non-2xx with an empty body (a
      // proxy's 502, a bare 413) leaves it undefined while still not saving
      // anything. The status is the authority, not the body.
      if (error !== undefined || !response.ok) {
        if (pending.current === null) pending.current = body;
        setStatus("failed");
        return "failed";
      }
      if (pending.current === body) {
        pending.current = null;
        setStatus("saved");
      } else {
        // A newer body is waiting: this answer saved older text, and saying
        // "Gespeichert" over the newer, unsent sentence would be the lie this
        // hook exists to remove. Its flush says so when it lands.
        setStatus("pending");
      }
      saved.current?.(target, body);
      return "saved";
    } catch {
      if (attemptGeneration !== generation.current) return "stale";
      if (pending.current === null) pending.current = body;
      setStatus("failed");
      return "failed";
    }
  }, []);

  const flush = useCallback((): Promise<FlushOutcome> => {
    if (timer.current !== null) {
      clearTimeout(timer.current);
      timer.current = null;
    }
    const next = writes.current.then(() => attempt());
    writes.current = next;
    return next;
  }, [attempt]);

  const schedule = useCallback(
    (body: string) => {
      pending.current = body;
      // A failure stays named while its body waits for the retry — a message
      // that vanishes on the next keystroke and returns 800 ms later is
      // flicker, not information. Only a flushed success clears it.
      setStatus((s) => (s === "failed" ? "failed" : "pending"));
      if (timer.current !== null) clearTimeout(timer.current);
      timer.current = window.setTimeout(() => void flush(), DELAY_MS);
    },
    [flush],
  );

  /** Drop the unsaved body: the user chose to leave it behind. */
  const discard = useCallback(() => {
    pending.current = null;
    generation.current += 1;
    setStatus("idle");
  }, []);

  // What stays here of the guards is the retry while the tab lives: a tab
  // hidden mid-debounce flushes now, because nothing may type it back to
  // life. The unload prompt belongs to the page (one owner for leaving).
  useEffect(() => {
    function onHidden() {
      if (document.visibilityState === "hidden") void flush();
    }
    document.addEventListener("visibilitychange", onHidden);
    return () => {
      document.removeEventListener("visibilitychange", onHidden);
      // Retire every answer still in flight first, then send the last body:
      // this flush's own attempt is captured after the bump, so it lands —
      // the earlier ones do not.
      generation.current += 1;
      void flush();
    };
  }, [flush]);

  return { status, schedule, flush, discard };
}

export function SaveIndicator({ status }: { status: SaveStatus }) {
  const t = useTranslation();
  if (status === "failed") {
    return (
      <p role="alert" className="text-sm text-danger">
        {t("save.failed")}
      </p>
    );
  }
  if (status === "idle" || status === "pending") return null;
  return (
    <span role="status" className="text-sm text-muted">
      {t(status === "saving" ? "save.saving" : "save.saved")}
    </span>
  );
}
