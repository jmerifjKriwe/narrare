/**
 * The read-only workspace (W4 Task 11) — the scene-centric writing surface
 * at `/novels/$novelId`, ported 1:1 from the round's harmonized authority
 * (`workspace-scene-centric`, light face wins; the dark rides the tokens'
 * light-dark pairs) onto the shell's tokens, inside the app-wide chrome.
 *
 * Three columns, one page: the explorer (identity, daily ring, tension
 * card, scene tree, shelf mini-card), the editor (ribbon + paper stage,
 * read-only until Task 12's TipTap), the inspector dock (round geometry
 * with the gap doc's neutrals, the cover miniature real).
 *
 * The page's one selection rule: the active scene defaults to the
 * LAST-EDITED one (updated_at — the hero door's own rule, gap row 3);
 * clicking a scene or a chapter selects it locally. The editor is LIVE
 * (Task 12): the active scene's body is edited through TipTap, debounced
 * into the scene's PUT by `useAutosave`, whose status feeds the one shell
 * store the chrome's three sync faces read.
 *
 * The continuation is LIVE (Task 16): the prompt bar's ask streams into
 * the ghost preview at the active scene's tail (the page's
 * `useContinuation`); Tab accepts into the autosave chain — the one write
 * path — Esc dismisses before the leave guard's own Esc, and typing
 * dismisses. A scene switch retires the ghost: it belongs to the tail it
 * was asked for. Every ask FLUSHES the autosave first (the leave guard's
 * flush-first rule): the server continues the saved body, and a failed
 * save keeps the ask home — the writer saves first.
 *
 * The zen room is LIVE (Task 18, D19): F9 toggles it, Esc exits — the
 * ghost owns Esc first, the guard and the dialogs own theirs, the room
 * exits last. Entry and exit both FLUSH the autosave and let the scene
 * cache catch up before the surface swaps (each face's editor initializes
 * from the cache on mount — a stale remount would drop unsaved words); a
 * failed exit flush raises the same guard: stay in zen, or discard and
 * go. The room mounts OVER the columns — one live editor at a time, the
 * page's one autosave and one continuation serve both faces.
 *
 * The tree's CRUD is LIVE (Task 13): the page owns the writes the explorer
 * asks for — create (chapter zero scenes, D16's empty-chapter face the
 * canonical new chapter; scene under the active chapter), the rename and
 * metadata dialogs, the delete confirms (scene always allowed, chapter
 * cascades), and the reorder (the optimistic whole-set order, the 409's
 * stored-ids revert, the refusal's restore, the honest notice + retry).
 * A create or a delete that moves the selection flushes or discards the
 * autosave draft first — a dead scene's words never reach the wire. The
 * setters wait for Task 19, named in code.
 *
 * The leave guard (WP0b's rule, the states sheet's Kachel 10): a leave —
 * a scene/chapter switch, any route navigation (the router blocker, which
 * also carries the browser's unload prompt) — first FLUSHES a healthy
 * pending body; only a write that actually failed raises the dialog.
 * „Bleiben" stays, „Verwerfen und verlassen" drops the draft and goes. A
 * refused body stays in memory until a retry lands it, so the error card's
 * reassurance („Deine Änderungen bleiben im Editor …") is true.
 *
 * The reads: the novel row (a 404 degrades to the shelf with the
 * deleted-elsewhere note — the query seam's documented contract), the
 * chapters in position order, one scene list per chapter, the activity
 * aggregate (the ring) and planning's storyboard (the tension label,
 * read-only HTTP composition — no capability import). Loading stands in
 * the states sheet's skeleton, error in its honest retry card (#887's
 * fictional offline claim never ships).
 */
import { getRouteApi, useBlocker, useNavigate } from "@tanstack/react-router";
import { useCallback, useEffect, useRef, useState } from "react";

import type { Chapter, Scene } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import {
  activeChapterFallback,
  noteNovelDeletedElsewhere,
  queryClient,
  useActivityQuery,
  useChaptersQuery,
  useNovelQuery,
} from "@shell/lib/query";

import { EditorColumn } from "./EditorColumn";
import { ExplorerColumn } from "./ExplorerColumn";
import { InspectorDock } from "./InspectorDock";
import { DeleteTreeDialog, TreeEditDialog } from "./TreeDialogs";
import { useAutosave } from "./useAutosave";
import {
  lastEditedEntry,
  orderedSceneEntries,
  rowsInOrder,
  scenesByChapterFrom,
  useChapterScenes,
  useContinuation,
  useCreateChapter,
  useCreateScene,
  useReorderChapters,
  useReorderScenes,
  useStoryboardQuery,
  type SceneEntry,
  type TreeNotice,
} from "./workspace";
import { LeaveGuardDialog, WorkspaceError, WorkspaceLoading } from "./WorkspaceStates";
import { ZenMode } from "./ZenMode";

const routeApi = getRouteApi("/novels/$novelId");

/** The page's local selection — a scene, a chapter (its first scene or the
 *  empty-chapter face), or null (the last-edited default). */
type Selection = { kind: "scene" | "chapter"; id: string } | null;

/** The tree's dialogs — the row menu's hand-off, the opener id the menu
 *  trigger's (the dialog's focus return). */
type CrudDialog =
  | { kind: "editChapter"; chapter: Chapter; openerId: string }
  | { kind: "editScene"; entry: SceneEntry; openerId: string }
  | { kind: "deleteChapter"; chapter: Chapter; openerId: string }
  | { kind: "deleteScene"; entry: SceneEntry; openerId: string }
  | null;

/** Every zen exit's focus return — the ribbon door that opened the room
 *  (the dialogs' own focus-return discipline). ONE home: the healthy exit
 *  and the guard's discard branch both leave through here, so no exit
 *  strand the focus on the body. rAF: the columns render in the same
 *  commit the room leaves, the door exists one frame later. */
function returnFocusToDesk(): void {
  window.requestAnimationFrame(() => document.getElementById("workspace-focus-door")?.focus());
}

export function WorkspacePage() {
  const t = useTranslation();
  const { novelId } = routeApi.useParams();
  const navigate = useNavigate();

  const novel = useNovelQuery(novelId);
  const chapters = useChaptersQuery(novelId);
  const chapterList: readonly Chapter[] = chapters.data ?? [];
  const sceneResults = useChapterScenes(chapterList);
  const activity = useActivityQuery();
  const storyboard = useStoryboardQuery(novelId);

  usePageTitle(novel.data?.title ?? t("writing.workspace.pageTitle"));

  const [selection, setSelection] = useState<Selection>(null);
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(new Set());
  // A scene/chapter switch whose flush failed waits here for the guard's
  // answer — the target the user asked for, held until they stay or discard.
  const [pendingSelect, setPendingSelect] = useState<Selection>(null);
  // Task 13: the tree's dialog and the honest notice under the tree.
  const [dialog, setDialog] = useState<CrudDialog>(null);
  const [notice, setNotice] = useState<TreeNotice | null>(null);
  // Task 18: the zen room (D19 — F9 toggles, Esc exits). A failed exit
  // flush waits here for the guard's answer, the pendingSelect discipline.
  const [zen, setZen] = useState(false);
  const [pendingZenExit, setPendingZenExit] = useState(false);

  // A navigation between two books reuses this component — the selection
  // and the collapse state belong to the book that was opened, never the
  // next one.
  // biome-ignore lint/correctness/useExhaustiveDependencies: novelId is the deliberate re-run key, not a value the body reads — a book switch must reset the selection.
  useEffect(() => {
    setSelection(null);
    setCollapsed(new Set());
    setPendingSelect(null);
    setDialog(null);
    setNotice(null);
    setZen(false);
    setPendingZenExit(false);
  }, [novelId]);

  // The 404 degrade — the book was deleted elsewhere: the shelf's note
  // seam records it, the navigation lands on the current truth. The render
  // below holds null while the effect runs, never a flash of error card.
  const novelStatus = (novel.error as { status?: number } | null)?.status;
  useEffect(() => {
    if (novel.isError && novelStatus === 404) {
      noteNovelDeletedElsewhere();
      void navigate({ to: "/", replace: true });
    }
  }, [novel.isError, novelStatus, navigate]);

  const entries = orderedSceneEntries(chapterList, scenesByChapterFrom(chapterList, sceneResults));
  const lastEdited = lastEditedEntry(entries);
  const scenesPending = sceneResults.some((result) => result.isPending);
  const scenesError = sceneResults.some((result) => result.isError);

  // The selection resolves against the entries: a scene stands for itself,
  // a chapter for its first scene in position order (or the empty-chapter
  // face), null for the last-edited default. With no scene at all, the
  // last-edited CHAPTER carries the empty-chapter face (D16).
  let activeEntry: SceneEntry | null = null;
  let activeChapter: Chapter | null = null;
  if (selection?.kind === "scene") {
    activeEntry = entries.find((entry) => entry.scene.id === selection.id) ?? lastEdited;
  } else if (selection?.kind === "chapter") {
    activeChapter = chapterList.find((chapter) => chapter.id === selection.id) ?? null;
    activeEntry = entries.find((entry) => entry.chapter.id === selection.id) ?? null;
  } else {
    activeEntry = lastEdited;
  }
  if (activeEntry !== null) activeChapter = activeEntry.chapter;
  else if (activeChapter === null) {
    const fallbackId = activeChapterFallback([...chapterList]);
    activeChapter = chapterList.find((chapter) => chapter.id === fallbackId) ?? null;
  }

  // The autosave lives at the page, not the editor: its lifetime matches the
  // page, and the leave guards sit next to the paths that change the
  // selection. The active scene's id/chapter feed the write; null on the
  // empty faces asks nothing. The status mirrors into the one shell store
  // the chrome reads (the hook owns that seam).
  const autosave = useAutosave(
    activeEntry?.scene.id ?? null,
    activeEntry?.chapter.id ?? null,
    novelId,
  );
  // The continuation lives beside the autosave (Task 16): one ghost for the
  // active scene, retired on a switch. The ghost is never an unsaved edit —
  // it stands outside the document until Tab accepts, and the acceptance
  // rides the autosave chain like any typed edit (the one write path). The
  // ask is save-first: the hook flushes the autosave before every start and
  // retry (the leave guard's own rule) — the server continues the SAVED
  // body, and a failed save keeps the ask home.
  const continuation = useContinuation(activeEntry?.scene.id ?? null, autosave.flush);
  // The blocker reads the live autosave through a ref, so its callbacks stay
  // stable (a fresh closure per render would re-register the history block).
  const autosaveRef = useRef(autosave);
  autosaveRef.current = autosave;

  // A route leave (the rail's switcher, the topbar's Manuscripts link, the
  // shelf mini-card, the browser's back) flushes a healthy pending body
  // first; only a failed write blocks. The resolver then raises the guard.
  const shouldBlock = useCallback(async () => {
    const save = autosaveRef.current;
    if (!save.unsaved) return false;
    const outcome = await save.flush();
    return outcome === "failed";
  }, []);
  const enableBeforeUnload = useCallback(() => autosaveRef.current.unsaved, []);
  const blocker = useBlocker({ shouldBlockFn: shouldBlock, enableBeforeUnload, withResolver: true });

  // A scene/chapter switch is local state, not a route change — the same
  // flush-first rule guards it. A failed flush holds the target for the
  // dialog; a healthy one selects straight away.
  const requestSelect = useCallback(
    (next: Selection) => {
      void autosaveRef.current.flush().then((outcome) => {
        if (outcome === "failed") setPendingSelect(next);
        else setSelection(next);
      });
    },
    [],
  );

  // --- The zen room (Task 18, D19) -----------------------------------------
  // F9 toggles the room, Esc exits — both flush FIRST (the leave guard's
  // own rule): the room's editor and the workspace's editor each initialize
  // from the cache on mount, so the draft must land and the cache catch up
  // before the surface swaps — a remount on a stale body would drop the
  // unsaved words from the document. A failed entry flush keeps the room
  // closed (the autosave's failure face stands — the writer saves first);
  // a failed exit flush raises the guard: stay in zen, or discard and go.
  const requestZenEntry = useCallback(() => {
    const target = activeEntryRef.current;
    if (target === null) return;
    void autosaveRef.current.flush().then(async (outcome) => {
      if (outcome === "failed") return;
      await queryClient.invalidateQueries({ queryKey: ["scenes", target.chapter.id] });
      setZen(true);
    });
  }, []);

  const requestZenExit = useCallback(() => {
    const target = activeEntryRef.current;
    void autosaveRef.current.flush().then(async (outcome) => {
      if (outcome === "failed") {
        setPendingZenExit(true);
        return;
      }
      if (target !== null) {
        await queryClient.invalidateQueries({ queryKey: ["scenes", target.chapter.id] });
      }
      setZen(false);
      returnFocusToDesk();
    });
  }, []);

  // The room's keyboard contract, read through refs so the listener stays
  // stable. The order is the draft's and the ghost's own: the ghost's
  // capture-phase Esc dismisses BEFORE anything here (and stops the
  // event); when the event targets the document itself, this handler
  // defers while a ghost stands, so the ghost's listener still runs first.
  // The guard and the dialogs own their Esc next; the room exits last.
  // In fullscreen the browser's Esc leaves fullscreen first (the draft's
  // dark face pins the rule).
  const zenRef = useRef(zen);
  zenRef.current = zen;
  const continuationRef = useRef(continuation);
  continuationRef.current = continuation;
  const activeEntryRef = useRef(activeEntry);
  activeEntryRef.current = activeEntry;
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.repeat) return;
      if (event.key === "F9") {
        if (guardRef.current !== null || dialogRef.current !== null) return;
        if (activeEntryRef.current === null) return;
        event.preventDefault();
        if (zenRef.current) requestZenExit();
        else requestZenEntry();
        return;
      }
      if (event.key === "Escape" && zenRef.current) {
        if (continuationRef.current.phase !== "idle") return;
        if (guardRef.current !== null || dialogRef.current !== null) return;
        if (document.fullscreenElement) return;
        event.preventDefault();
        requestZenExit();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [requestZenEntry, requestZenExit]);

  // The one guard, two triggers: a blocked route leave or a failed switch.
  // „Bleiben" resets the leave; „Verwerfen und verlassen" drops the draft
  // (so the unmount flush cannot re-send it) and then goes.
  const guard =
    blocker.status === "blocked"
      ? {
          stay: () => blocker.reset(),
          discard: () => {
            autosave.discard();
            blocker.proceed();
          },
        }
      : pendingSelect !== null
        ? {
            stay: () => setPendingSelect(null),
            discard: () => {
              autosave.discard();
              setSelection(pendingSelect);
              setPendingSelect(null);
            },
          }
        : pendingZenExit
          ? {
              stay: () => setPendingZenExit(false),
              discard: () => {
                autosave.discard();
                setPendingZenExit(false);
                setZen(false);
                // The discard exit returns the desk's focus too — the
                // guard's own opener-restore no-ops here (its opener node
                // left with the room), so the exit's rule carries it.
                returnFocusToDesk();
              },
            }
          : null;
  // The keyboard contract reads the live guard and dialog through refs —
  // a room's Esc defers to whichever owns the ask (the listener above).
  const guardRef = useRef(guard);
  guardRef.current = guard;
  const dialogRef = useRef(dialog);
  dialogRef.current = dialog;

  // --- The tree's CRUD (Task 13) — the page owns the writes ---------------
  //
  // The explorer asks, the page writes: the mutations live in the
  // workspace seam (one home beside the reads), the selection moves here
  // because the autosave draft belongs to the page. A create selects the
  // new row through the flush-first rule (requestSelect); a delete of the
  // active row DISCARDS its draft — the words go with the row, never onto
  // the wire of a scene that no longer exists — and selects the neighbour.

  const createChapter = useCreateChapter(novelId);
  const createScene = useCreateScene(novelId);
  const reorderChapters = useReorderChapters(novelId);
  const reorderScenes = useReorderScenes(novelId);
  const createBusy = createChapter.isPending || createScene.isPending;
  const reorderBusy = reorderChapters.isPending || reorderScenes.isPending;

  function handleCreateChapter() {
    setNotice(null);
    createChapter.mutate(undefined, {
      // The new chapter opens on its empty-chapter face (D16) — the
      // canonical new-chapter experience, no auto-created scene.
      onSuccess: (chapter) => requestSelect({ kind: "chapter", id: chapter.id }),
      onError: () => setNotice({ kind: "createChapterFailed" }),
    });
  }

  function handleCreateScene(chapterId: string) {
    setNotice(null);
    createScene.mutate(
      { chapterId },
      {
        onSuccess: (scene) => {
          // The new scene is selected — its row must be visible, so the
          // chapter opens (the select-a-chapter rule's own discipline).
          setCollapsed((previous) => {
            if (!previous.has(chapterId)) return previous;
            const next = new Set(previous);
            next.delete(chapterId);
            return next;
          });
          requestSelect({ kind: "scene", id: scene.id });
        },
        onError: () => setNotice({ kind: "createSceneFailed", chapterId }),
      },
    );
  }

  /** The scene delete landed: the active scene's draft dies with it, the
   *  selection moves to the chapter's next scene (position order, the
   *  previous one when the deleted was the last) or the empty-chapter
   *  face. A non-active delete leaves the selection alone. */
  function afterSceneDelete(entry: SceneEntry) {
    if (activeEntry?.scene.id === entry.scene.id) {
      autosave.discard();
      const siblings = (scenesByChapterFrom(chapterList, sceneResults).get(entry.chapter.id) ?? [])
        .filter((scene) => scene.id !== entry.scene.id)
        .sort((a, b) => a.position - b.position);
      const next =
        siblings.find((scene) => scene.position > entry.scene.position) ??
        siblings[siblings.length - 1] ??
        null;
      setSelection(next !== null ? { kind: "scene", id: next.id } : { kind: "chapter", id: entry.chapter.id });
    } else if (selection?.kind === "scene" && selection.id === entry.scene.id) {
      setSelection(null);
    }
  }

  /** The chapter delete landed (its scenes cascaded): the draft of a scene
   *  inside it dies with it, the selection moves to the next chapter (its
   *  first scene or empty face) — or the empty book when the last chapter
   *  went. The dead chapter's scene list is retired by the mutation seam. */
  function afterChapterDelete(chapter: Chapter) {
    const activeInside = activeEntry?.chapter.id === chapter.id;
    const emptyFaceOnIt = activeEntry === null && activeChapter?.id === chapter.id;
    if (activeInside) autosave.discard();
    if (activeInside || emptyFaceOnIt) {
      const survivors = chapterList.filter((row) => row.id !== chapter.id);
      const next =
        survivors.find((row) => row.position > chapter.position) ?? survivors[survivors.length - 1] ?? null;
      setSelection(next !== null ? { kind: "chapter", id: next.id } : null);
    } else if (selection?.kind === "chapter" && selection.id === chapter.id) {
      setSelection(null);
    }
  }

  /** One arrangement on the wire: the optimistic whole-set order into the
   *  cache (positions renumbered), the PUT behind it. A 409 reverts to the
   *  stored ids the server named — or refetches when they name a row the
   *  cache lacks (the second tab's addition); any other refusal restores
   *  the pre-drag order. Both leave the honest notice; the retry re-runs
   *  the very ask (the conflict's retry asks the truth again). */
  function commitReorder(level: "chapters" | "scenes", chapterId: string | null, ids: string[]) {
    if (reorderBusy) return;
    setNotice(null);
    const key = level === "chapters" ? ["chapters", novelId] : ["scenes", chapterId];
    const base = level === "chapters" ? 0 : 1;
    const snapshot = queryClient.getQueryData<(Chapter | Scene)[]>(key);
    if (snapshot === undefined) return;
    const snapshotIds = snapshot.map((row) => row.id);
    const optimistic = rowsInOrder(snapshot, ids, base);
    if (optimistic === null) {
      void queryClient.invalidateQueries({ queryKey: key });
      return;
    }
    queryClient.setQueryData(key, optimistic);
    const write =
      level === "chapters"
        ? reorderChapters.mutateAsync(ids)
        : reorderScenes.mutateAsync({ chapterId: chapterId as string, ids });
    void write.catch((error: unknown) => {
      const status = (error as { status?: number }).status;
      const storedIds = (error as { storedIds?: string[] | null }).storedIds ?? null;
      // The current cache may carry fresher counts than the snapshot (a
      // save landed mid-flight) — restore the ORDER onto the freshest rows.
      const current = queryClient.getQueryData<(Chapter | Scene)[]>(key) ?? snapshot;
      if (status === 409) {
        const stored = storedIds !== null ? rowsInOrder(current, storedIds, base) : null;
        if (stored !== null) queryClient.setQueryData(key, stored);
        else void queryClient.invalidateQueries({ queryKey: key });
        setNotice({ kind: "reorderConflict" });
      } else {
        const restored = rowsInOrder(current, snapshotIds, base);
        if (restored !== null) queryClient.setQueryData(key, restored);
        else void queryClient.invalidateQueries({ queryKey: key });
        setNotice({ kind: "reorderFailed", level, chapterId, ids });
      }
    });
  }

  function retryNotice() {
    if (notice === null) return;
    switch (notice.kind) {
      case "createChapterFailed":
        handleCreateChapter();
        break;
      case "createSceneFailed":
        handleCreateScene(notice.chapterId);
        break;
      case "reorderConflict":
        // The truth moved — ask it again, never re-send the stale order.
        setNotice(null);
        void queryClient.invalidateQueries({ queryKey: ["chapters", novelId] });
        void queryClient.invalidateQueries({ queryKey: ["scenes"] });
        break;
      case "reorderFailed":
        commitReorder(notice.level, notice.chapterId, notice.ids);
        break;
    }
  }

  // The retry keeps the error card on screen while the asks run (a v5
  // refetch clears the error into pending — the flag holds the panel, the
  // shelf's own discipline). Every read the page owns asks again.
  const [retrying, setRetrying] = useState(false);
  const lastError = useRef("");
  const failure = novel.error ?? chapters.error ?? sceneResults.find((result) => result.error)?.error;
  if (failure) lastError.current = failure instanceof Error ? failure.message : String(failure);
  function retry() {
    setRetrying(true);
    void Promise.all([
      novel.refetch(),
      chapters.refetch(),
      ...sceneResults.map((result) => result.refetch()),
      activity.refetch(),
      storyboard.refetch(),
    ]).finally(() => setRetrying(false));
  }

  const readsReady = novel.isSuccess && chapters.isSuccess && !scenesPending && !scenesError;
  const failed = (novel.isError && novelStatus !== 404) || chapters.isError || scenesError;
  const showError = (failed || retrying) && !readsReady;
  const showLoading = !readsReady && !showError;

  if (novel.isError && novelStatus === 404) return null;
  if (showLoading) return <WorkspaceLoading />;
  if (showError) {
    return <WorkspaceError message={lastError.current} retrying={retrying} onRetry={retry} />;
  }
  if (novel.data == null) return null;

  // Every prose edit rides the one path: typing dismisses the ghost (design
  // G4 — the writer's own words win over the proposal, a running stream
  // aborts with it), the autosave owns the wire. The zen room's editor and
  // the workspace's editor feed the same door.
  function handleBodyChange(body: string) {
    continuation.dismiss();
    autosave.schedule(body);
  }

  return (
    <>
      {zen && activeEntry !== null ? (
        /* The zen room (Task 18) — mounted OVER the workspace: the columns
           yield (one live editor at a time — two would double the ghost's
           keyboard contract), the chrome stays covered beneath the fixed
           surface. The counters read the aggregate the page already owns. */
        <ZenMode
          novel={novel.data}
          entry={activeEntry}
          todayWords={activity.data?.today_words ?? null}
          continuation={continuation}
          onBodyChange={handleBodyChange}
          onExit={requestZenExit}
        />
      ) : (
        <div className="flex h-full overflow-hidden">
          <ExplorerColumn
            novel={novel.data}
            chapters={chapterList}
            sceneResults={sceneResults}
            entries={entries}
            activeSceneId={activeEntry?.scene.id ?? null}
            activeChapterId={activeChapter?.id ?? null}
            collapsed={collapsed}
            onToggleChapter={(chapterId) => {
              setCollapsed((previous) => {
                const next = new Set(previous);
                if (next.has(chapterId)) next.delete(chapterId);
                else next.add(chapterId);
                return next;
              });
            }}
            onSelectChapter={(chapterId) => {
              requestSelect({ kind: "chapter", id: chapterId });
              // Selecting a chapter opens it — a collapsed card reveals its rows.
              setCollapsed((previous) => {
                if (!previous.has(chapterId)) return previous;
                const next = new Set(previous);
                next.delete(chapterId);
                return next;
              });
            }}
            onSelectScene={(sceneId) => requestSelect({ kind: "scene", id: sceneId })}
            onCreateChapter={handleCreateChapter}
            onCreateScene={handleCreateScene}
            onEditChapter={(chapter, openerId) => setDialog({ kind: "editChapter", chapter, openerId })}
            onEditScene={(entry, openerId) => setDialog({ kind: "editScene", entry, openerId })}
            onDeleteChapter={(chapter, openerId) => setDialog({ kind: "deleteChapter", chapter, openerId })}
            onDeleteScene={(entry, openerId) => setDialog({ kind: "deleteScene", entry, openerId })}
            onReorderChapters={(ids) => commitReorder("chapters", null, ids)}
            onReorderScenes={(chapterId, ids) => commitReorder("scenes", chapterId, ids)}
            reorderBusy={reorderBusy}
            createBusy={createBusy}
            notice={notice}
            onNoticeRetry={retryNotice}
            onNoticeDismiss={() => setNotice(null)}
            activity={activity}
            storyboard={storyboard}
          />
          <EditorColumn
            novel={novel.data}
            entry={activeEntry}
            emptyChapter={chapterList.length > 0 && activeEntry === null}
            status={autosave.status}
            onRetry={() => void autosave.flush()}
            onBodyChange={handleBodyChange}
            onCreateScene={() => {
              if (activeChapter !== null) handleCreateScene(activeChapter.id);
            }}
            onEnterZen={requestZenEntry}
            continuation={continuation}
          />
          <InspectorDock novel={novel.data} />
        </div>
      )}
      {/* The guard and the dialogs ride over BOTH faces — a blocked route
          leave asks the same question whether the room is zen or the desk. */}
      {guard !== null && <LeaveGuardDialog onStay={guard.stay} onDiscard={guard.discard} />}
      {dialog?.kind === "editChapter" && (
        <TreeEditDialog
          novelId={novelId}
          target={{ kind: "chapter", chapter: dialog.chapter }}
          openerId={dialog.openerId}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog?.kind === "editScene" && (
        <TreeEditDialog
          novelId={novelId}
          target={{ kind: "scene", entry: dialog.entry }}
          openerId={dialog.openerId}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog?.kind === "deleteChapter" && (
        <DeleteTreeDialog
          novelId={novelId}
          target={{ kind: "chapter", chapter: dialog.chapter }}
          openerId={dialog.openerId}
          onClose={() => setDialog(null)}
          onDeleted={() => afterChapterDelete(dialog.chapter)}
        />
      )}
      {dialog?.kind === "deleteScene" && (
        <DeleteTreeDialog
          novelId={novelId}
          target={{ kind: "scene", entry: dialog.entry }}
          openerId={dialog.openerId}
          onClose={() => setDialog(null)}
          onDeleted={() => afterSceneDelete(dialog.entry)}
        />
      )}
    </>
  );
}
