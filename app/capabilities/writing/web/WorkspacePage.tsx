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
 * store the chrome's three sync faces read. The create doors, the reorder
 * grips and the setters wait for Tasks 13/19, each named in code.
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

import type { Chapter } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import {
  activeChapterFallback,
  noteNovelDeletedElsewhere,
  useActivityQuery,
  useChaptersQuery,
  useNovelQuery,
} from "@shell/lib/query";

import { EditorColumn } from "./EditorColumn";
import { ExplorerColumn } from "./ExplorerColumn";
import { InspectorDock } from "./InspectorDock";
import { useAutosave } from "./useAutosave";
import {
  lastEditedEntry,
  orderedSceneEntries,
  scenesByChapterFrom,
  useChapterScenes,
  useStoryboardQuery,
  type SceneEntry,
} from "./workspace";
import { LeaveGuardDialog, WorkspaceError, WorkspaceLoading } from "./WorkspaceStates";

const routeApi = getRouteApi("/novels/$novelId");

/** The page's local selection — a scene, a chapter (its first scene or the
 *  empty-chapter face), or null (the last-edited default). */
type Selection = { kind: "scene" | "chapter"; id: string } | null;

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

  // A navigation between two books reuses this component — the selection
  // and the collapse state belong to the book that was opened, never the
  // next one.
  // biome-ignore lint/correctness/useExhaustiveDependencies: novelId is the deliberate re-run key, not a value the body reads — a book switch must reset the selection.
  useEffect(() => {
    setSelection(null);
    setCollapsed(new Set());
    setPendingSelect(null);
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
        : null;

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

  return (
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
        activity={activity}
        storyboard={storyboard}
      />
      <EditorColumn
        novel={novel.data}
        entry={activeEntry}
        emptyChapter={chapterList.length > 0 && activeEntry === null}
        status={autosave.status}
        onRetry={() => void autosave.flush()}
        onBodyChange={autosave.schedule}
      />
      <InspectorDock novel={novel.data} />
      {guard !== null && <LeaveGuardDialog onStay={guard.stay} onDiscard={guard.discard} />}
    </div>
  );
}
