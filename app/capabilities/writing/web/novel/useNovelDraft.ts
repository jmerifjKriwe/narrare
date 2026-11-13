import { useBlocker } from "@tanstack/react-router";
import { useCallback, useEffect, useRef, useState } from "react";

import type { Chapter } from "@shell/lib/api/client";
import { queryClient } from "@shell/lib/query";
import { useAutosave, unsavedStatus, type DocumentDraft } from "@shell/lib/save";

/**
 * The open chapter's draft and its guards: the autosave, the held draft the
 * editor shows, the leave guard's blocker and the rename answer. Takes the
 * novel id and the open chapter; the page passes `status`, `draft`,
 * `changeTitle` and `schedule` to the editor, rail and dialogs.
 */
export function useNovelDraft(novelId: string, current: Chapter | null) {
  // The latest held draft, read at patch time so a rename that landed after
  // the flush was scheduled still reaches the cache (#687).
  const latestDraft = useRef<DocumentDraft>({ title: "", body: "" });
  const remember = useCallback(
    (chapterId: string, draft: DocumentDraft) => {
      const settled = latestDraft.current.title !== "" || latestDraft.current.body !== "" ? latestDraft.current : draft;
      // The saved draft reaches the cache before the ask: the patch makes
      // the settled document — title and body both — the key's own answer,
      // so the words, the row's name and the freshness their updated_at
      // stands for cannot be remounted over by a refetch that never
      // answers (or answers refused) on a later switch. The refetch stays
      // the truth; the patch only holds the page's ground until it lands.
      queryClient.setQueryData<Array<Chapter>>(["chapters", novelId], (rows) =>
        rows?.map((row) =>
          row.id === chapterId
            ? { ...row, ...settled, title: settled.title.trim(), updated_at: new Date().toISOString() }
            : row,
        ),
      );
      // This callback is `onSaved` — it fires only on success — so a failed
      // save never asks for anything.
      void queryClient.invalidateQueries({ queryKey: ["chapters", novelId] });
      // Same truth as the create path above: a settled save advanced the
      // novel's updated_at, and the shelf's hero reads it through ["novels"].
      void queryClient.invalidateQueries({ queryKey: ["novels"] });
    },
    [novelId],
  );

  // The autosave is the page's, not the chapter's: the editor remounts on
  // every switch (its key is the chapter id), and a hook that lived inside
  // it would unmount with it — cleanup firing, a refused body dying with
  // its ref — on each switch. Here the body's lifetime spans switches: the
  // editor shows `status` beside the text and feeds `schedule` on update;
  // `flush` is the page's own handle on what has not reached the server.
  const { status, schedule: saveSchedule, flush, discard } = useAutosave(
    current?.id ?? null,
    remember,
  );

  // The document the writer holds: title beside body, one draft — the
  // autosave's unit of work. It belongs to the open chapter, and the
  // selection's change is its reset, done in render (the state-adjust
  // pattern) so the new chapter's first paint already carries its own
  // name: an effect would paint the old book's title over the new chapter
  // for a frame. Every schedule — the editor's body, the runhead's title —
  // passes through one wrapper, so the state and the pending save can
  // never disagree: `remember` patches the row from the whole draft, and a
  // stale half would patch a regression.
  const [held, setHeld] = useState<{ id: string | null; draft: DocumentDraft }>({
    id: null,
    draft: { title: "", body: "" },
  });
  const currentId = current?.id ?? null;
  if (held.id !== currentId) {
    setHeld({
      id: currentId,
      draft: { title: current?.title ?? "", body: current?.body ?? "" },
    });
  }
  const draft = held.draft;
  latestDraft.current = draft;
  const draftRef = useRef(draft);
  draftRef.current = draft;
  const scheduleDraft = useCallback(
    (next: DocumentDraft, changed: keyof DocumentDraft) => {
      setHeld((previous) => ({ ...previous, draft: next }));
      saveSchedule(next, changed);
    },
    [saveSchedule],
  );
  /** The runhead's title keystrokes: the draft's body is whatever the page
   *  last held, so the rename rides beside — never over — the text. */
  const changeTitle = useCallback(
    (value: string) => scheduleDraft({ ...draftRef.current, title: value }, "title"),
    [scheduleDraft],
  );

  // The page's one opinion about unsaved text, shared by every guard: a body
  // waiting for its debounce, one on the wire, or one that did not land.
  // `saving` counts — a request that never answers loses the text just as
  // surely as one that was refused.
  const unsaved = unsavedStatus(status);
  // The guards ask at the moment they run, not at the render that registered
  // them: a navigation starts after the keystroke, not before it.
  const unsavedNow = useRef(unsaved);
  unsavedNow.current = unsaved;

  // The leave guard's state, ahead of the keyboard contract: while an ask
  // stands, F9/Esc are the dialog's keys, not the workbench's — a second
  // ask would overwrite the first answer's resolver and strand the
  // navigation that is still waiting on it.
  const [guardOpen, setGuardOpen] = useState(false);
  const guardAnswer = useRef<((leave: boolean) => void) | null>(null);
  const guardBusy = useRef(false);
  const answerGuard = useCallback((leave: boolean) => {
    setGuardOpen(false);
    guardBusy.current = false;
    const answer = guardAnswer.current;
    guardAnswer.current = null;
    answer?.(leave);
  }, []);

  // Every way out of the chapter — the rail, the docks and their panel
  // state, history's back and forward, the shell's links, and whatever
  // jump lands here later — is a router navigation, and this is the one
  // place they all pass. While text is unsaved the gate flushes first;
  // only a flush that did not land asks, and a dismissed ask keeps the
  // work. The destination does not matter, because the body does: anything
  // the router would move away from the editor is worth the same question.
  // An accepted ask does not drop the body here, either: a panel toggle
  // would wipe a refused write while the editor stayed mounted — the
  // notice retracting, the next leave asking nothing — so the body is
  // cleared only where the chapter really changes (the effect below) or
  // the page really goes (the autosave's own teardown).
  // `enableBeforeUnload` is the same question for the tab close, which has
  // no navigation to intercept.
  //
  // The ask itself is the shell's dialog (F21), not window.confirm: the
  // page's own clothes, focus contained while it stands, and the two
  // answers as the two buttons the question names. The blocker awaits the
  // answer as a promise; Escape and an outside click are RAC dismissals,
  // which land in `onOpenChange` as a "stay". `guardBusy` stands only
  // once the ask stands — it is set after a flush has failed, not while
  // it runs — so two navigations inside the flush window are last-wins
  // by design: the second ask replaces the first.
  useBlocker({
    shouldBlockFn: async () => {
      if (!unsavedNow.current) return false;
      if (guardBusy.current) return true;
      const outcome = await flush();
      if (outcome !== "failed") return false;
      guardBusy.current = true;
      const leave = await new Promise<boolean>((resolve) => {
        guardAnswer.current = resolve;
        setGuardOpen(true);
      });
      return !leave;
    },
    enableBeforeUnload: () => unsavedNow.current,
  });

  // Reset the save story only after the chapter selection actually changes.
  // Creation can fail after a confirmed leave; until it succeeds, the old
  // chapter's failed body must still be protected by every leave guard.
  // biome-ignore lint/correctness/useExhaustiveDependencies: semantic key — `current?.id` is the deliberate re-run key (a chapter change drops the old draft); `discard` is stable and cannot carry the key alone.
  useEffect(() => {
    discard();
  }, [current?.id, discard]);

  /** The rename dialog's answer: the runhead's input (and the page's held
   *  draft) take the server's title at once, while the autosave's pending
   *  slot keeps whatever fields it was holding — the title was never
   *  dirtied by the dialog, so the pending flush carries the body only
   *  and the rename survives it (Task 9's contract). */
  const rename = useCallback(
    (title: string) => {
      setHeld((previous) =>
        previous.id === current?.id
          ? { ...previous, draft: { ...previous.draft, title } }
          : previous,
      );
    },
    [current?.id],
  );

  return {
    status,
    schedule: scheduleDraft,
    flush,
    discard,
    draft,
    changeTitle,
    rename,
    unsaved,
    guardOpen,
    answerGuard,
  };
}
