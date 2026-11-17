/**
 * The scene autosave (W4 Task 12) — the WP0b semantics the backend contract
 * expects (`docs/superpowers/specs/2026-10-25-wp0b-autosave-design.md`),
 * re-owned for prose scenes: the chapter is the grouping shell now, the body
 * lives on the scene, and the PUT is the scene's own door.
 *
 * Debounced save that tells the truth about the answer: a refused or failed
 * write is `failed` — named beside the text — and the body it carried stays
 * in memory, so the next keystroke or a retry lands it. Success, and only
 * success, is `saved`. The endpoint is idempotent, so a duplicate flush costs
 * nothing. Writes are serialized: a flush that arrives while one is on the
 * wire waits for it and then carries the latest body — two overlapping PUTs
 * could answer out of order and let the older text win the server row.
 *
 * The status is the four-state vocabulary the one shell store speaks
 * (`saveStatus.ts`): `saving` covers the whole engaged window — the debounce
 * and the wire alike — so the leave guards can tell „nothing to lose"
 * (`idle`/`saved`) from „words only in the browser" (`saving`/`failed`).
 * A failure survives further keystrokes (no flicker); only a flushed success
 * clears it. The hook mirrors its status into the store for the chrome's
 * three faces and rests the store at idle when it goes away.
 *
 * Ownership: the hook lives at the page (WorkspacePage), not the editor —
 * its lifetime matches the page, and the leave guards (scene switch, the
 * router blocker, the unload prompt) sit next to the paths that change the
 * selection. The editor only feeds `schedule`; the page flushes before it
 * lets a leave through.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import { client } from "@shell/lib/api/client";
import { setSaveStatus, unsavedStatus, type SaveStatus } from "@shell/lib/saveStatus";

import { invalidateSceneReads } from "./workspace";

/** The debounce window. Exported so a test that must prove „past the
 *  debounce, nothing happened" waits on this constant instead of a copy of
 *  its value: change the window and the test follows it. */
export const AUTOSAVE_DELAY_MS = 800;

/** `stale` is an answer addressed to an attempt that is no longer the page's:
 *  the draft was discarded or the hook went away. It is neither a save nor a
 *  failure to ask the user about. */
export type FlushOutcome = "clean" | "saved" | "failed" | "stale";

export interface Autosave {
  status: SaveStatus;
  /** The one question every leave guard asks (unsavedStatus). */
  unsaved: boolean;
  /** Hand the latest body to the debounce; the wire waits out the window. */
  schedule: (body: string) => void;
  /** Settle the latest draft now — the leave paths await this. */
  flush: () => Promise<FlushOutcome>;
  /** Drop the unsaved draft: the user chose to leave it behind. */
  discard: () => void;
}

export function useAutosave(
  sceneId: string | null,
  chapterId: string | null,
  novelId: string | null,
): Autosave {
  const [status, setStatus] = useState<SaveStatus>("idle");
  const timer = useRef<number | null>(null);
  // The body awaiting the wire. Replaced, never patched in place — a newer
  // body mid-flight is a new attempt, and the reference tells them apart.
  const pending = useRef<string | null>(null);
  const id = useRef(sceneId);
  id.current = sceneId;
  const chapter = useRef(chapterId);
  chapter.current = chapterId;
  const novel = useRef(novelId);
  novel.current = novelId;
  // Bumped when the draft is dropped or the hook goes away: an answer that
  // lands after that belongs to an attempt nobody is waiting for.
  const generation = useRef(0);
  // The tail of the write queue. Never rejects: `attempt` resolves every path.
  const writes = useRef<Promise<FlushOutcome>>(Promise.resolve("clean"));

  /** Write the pending body once, retaining newer text and ignoring retired answers. */
  const attempt = useCallback(async (): Promise<FlushOutcome> => {
    const body = pending.current;
    const target = id.current;
    if (body === null || target === null) return "clean";
    // The body stays in `pending` until the answer: dropping it here is what
    // made a refused write unrecoverable. A body edited while this request is
    // in flight replaces it there and must survive the answer.
    const attemptGeneration = generation.current;
    setStatus("saving");
    try {
      const { error, response } = await client.PUT("/api/writing/scenes/{scene_id}", {
        params: { path: { scene_id: target } },
        body: { body },
      });
      if (attemptGeneration !== generation.current) return "stale";
      // `error` is the parsed error body; a non-2xx with an empty body (a
      // proxy's 502, a bare 413) leaves it undefined while still not saving
      // anything. The status is the authority, not the body.
      if (error !== undefined || !response.ok) {
        setStatus("failed");
        return "failed";
      }
      if (pending.current === body) {
        pending.current = null;
        setStatus("saved");
      } else {
        // A newer body is waiting: this answer saved older words, and saying
        // „Gespeichert" over the newer, unsent ones would be the lie this hook
        // exists to remove. Its flush says so when it lands.
        setStatus("saving");
      }
      if (chapter.current !== null && novel.current !== null) {
        invalidateSceneReads(chapter.current, novel.current);
      }
      return "saved";
    } catch {
      if (attemptGeneration !== generation.current) return "stale";
      setStatus("failed");
      return "failed";
    }
  }, []);

  /** Serialize writes and settle the latest draft before allowing a caller to leave. */
  const flush = useCallback((): Promise<FlushOutcome> => {
    if (timer.current !== null) {
      clearTimeout(timer.current);
      timer.current = null;
    }
    const next = writes.current.then(async () => {
      let outcome = await attempt();
      // Typing can replace the body while its PUT is in flight. A leave must
      // wait for that replacement too, and stop if any write fails.
      while (outcome === "saved" && pending.current !== null) {
        outcome = await attempt();
      }
      return outcome;
    });
    writes.current = next;
    return next;
  }, [attempt]);

  /** Keep the latest body and restart its debounce without hiding a failed save. */
  const schedule = useCallback(
    (body: string) => {
      pending.current = body;
      // A failure stays named while its body waits for the retry — a message
      // that vanishes on the next keystroke and returns 800 ms later is
      // flicker, not information. Only a flushed success clears it.
      setStatus((s) => (s === "failed" ? "failed" : "saving"));
      if (timer.current !== null) clearTimeout(timer.current);
      timer.current = window.setTimeout(() => void flush(), AUTOSAVE_DELAY_MS);
    },
    [flush],
  );

  /** Drop the unsaved draft: the user chose to leave it behind. */
  const discard = useCallback(() => {
    pending.current = null;
    generation.current += 1;
    if (timer.current !== null) {
      clearTimeout(timer.current);
      timer.current = null;
    }
    setStatus("idle");
  }, []);

  // The chrome's faces read the one store: mirror every status into it, and
  // rest it at idle when the editor goes away (the shelf's Ruhe face). The
  // mirror is an effect, so an in-flight answer that lands after unmount —
  // a no-op setState — cannot repaint the chrome of a page that is gone.
  useEffect(() => {
    setSaveStatus(status);
  }, [status]);
  useEffect(() => () => setSaveStatus("idle"), []);

  // What stays here of the guards is the retry while the tab lives: a tab
  // hidden mid-debounce flushes now, because nothing may type it back to
  // life. The unload prompt and the in-app leave belong to the page.
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

  return { status, unsaved: unsavedStatus(status), schedule, flush, discard };
}
