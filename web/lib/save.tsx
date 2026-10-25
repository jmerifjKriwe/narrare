import { useCallback, useEffect, useRef, useState } from "react";

import { client } from "./api/client";
import { useTranslation } from "./i18n";

export type SaveStatus = "idle" | "pending" | "saving" | "saved" | "failed";
export type FlushOutcome = "clean" | "saved" | "failed";

const DELAY_MS = 800;

/**
 * Debounced save that tells the truth about the answer: a refused or failed
 * write is `failed` — named beside the text — and the body it carried stays
 * in memory, so the next keystroke retries it. Success, and only success, is
 * `saved`. The endpoint is idempotent, so a duplicate flush costs nothing.
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
  // Bumped when the hook goes away: an answer that lands after that belongs
  // to a component that no longer exists and must not touch state.
  const generation = useRef(0);

  const flush = useCallback(async (): Promise<FlushOutcome> => {
    if (timer.current !== null) {
      clearTimeout(timer.current);
      timer.current = null;
    }
    const body = pending.current;
    const target = id.current;
    if (body === null || target === null) return "clean";
    // The body stays in `pending` until the answer: dropping it here is what
    // made a refused write unrecoverable. A body typed while this request is
    // in flight replaces it there and must survive the answer.
    const attempt = generation.current;
    setStatus("saving");
    try {
      const { error } = await client.PUT("/api/writing/chapters/{chapter_id}", {
        params: { path: { chapter_id: target } },
        body: { body },
      });
      if (attempt !== generation.current) return "failed";
      if (error !== undefined) {
        if (pending.current === null) pending.current = body;
        setStatus("failed");
        return "failed";
      }
      if (pending.current === body) pending.current = null;
      setStatus("saved");
      saved.current?.(target, body);
      return "saved";
    } catch {
      if (attempt !== generation.current) return "failed";
      if (pending.current === null) pending.current = body;
      setStatus("failed");
      return "failed";
    }
  }, []);

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

  useEffect(() => {
    function onHidden() {
      if (document.visibilityState === "hidden") void flush();
    }
    window.addEventListener("beforeunload", flush);
    document.addEventListener("visibilitychange", onHidden);
    return () => {
      window.removeEventListener("beforeunload", flush);
      document.removeEventListener("visibilitychange", onHidden);
      // Retire every answer still in flight first, then send the last body:
      // this flush's own attempt is captured after the bump, so it lands —
      // the earlier ones do not.
      generation.current += 1;
      void flush();
    };
  }, [flush]);

  return { status, schedule, flush };
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
