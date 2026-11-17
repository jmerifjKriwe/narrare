/**
 * The editor column (W4 Task 12, live) — the scene-centric draft's paper
 * stage on the shell's tokens: the 44px ribbon (breadcrumb + the derived
 * scene-code badge, the chapter-target pill, the tool doors), the scrolling
 * stage with the paper card (max-w 48rem), and the card's own anatomy:
 * running head, chapter/scene eyebrow, title, overline, sepia rule, the
 * editable drop-cap prose, foot.
 *
 * The prose is the ACTIVE scene's body, edited through TipTap (SceneEditor,
 * keyed per scene — a switch swaps the document, a save's refetch never
 * resets the caret). Every edit feeds the page's autosave (`onBodyChange`)
 * and moves the foot's live word count (the shared whitespace rule, the
 * same figure the server derives). The chapter stays the grouping shell.
 *
 * One save-status owner feeds three faces (D10): the foot's autosave line
 * here, the topbar chip and the rail sync dot read the same state through
 * the shell store. The foot speaks the draft's vocabulary — „Automatisch
 * gesichert" at rest, „Sicherung läuft …" while the write is engaged, and
 * KACHEL 9's red failure face with „Wiederholen" when a write refused (the
 * body stays in the editor until the retry lands). The ribbon carries
 * KACHEL 9's amber „Ungesicherte Änderungen" pill while words are unsaved.
 * Task 10's static foot interim ends here.
 *
 * Honest readings of the draft (the gap doc records them):
 * - The running head is `novel.author` beside the book (D22) — the book
 *   alone when no author stands. NO folio, NO page count (row 9).
 * - The chapter-target pill keeps the neutral „—": ChapterRead carries no
 *   target yet, and the setter is Task 19's (D20 places it inline here).
 *   Fokus waits for the zen wave (Task 18), Verlauf for the editing wave
 *   (INTERIM #875), Export for the production wave (INTERIM #876).
 * - The foot's autosave line carries no timestamp: the draft's „vor 1 Min."
 *   is a mock relative claim; the honest line names the state, not a clock.
 * - The ghost text and the prompt bar are LIVE (Task 16): the continuation
 *   streams into the tail preview (the page's hook owns the ask, the editor
 *   the Tab insertion), the floating bar carries the real prompt parameter
 *   (D5) with the neutral Stil trigger (INTERIM #878).
 *
 * The empty faces answer per `workspace-states` (Kacheln 3/4): the
 * unwritten work and the first-scene invitation. Kachel 4's create door
 * is LIVE (Task 13) — the empty chapter is the canonical new-chapter
 * experience (D16), and „+ Szene 1 anlegen" starts it.
 */

import type { Novel } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { activeLocale } from "@shell/lib/locale";
import { capitalizedWord } from "@shell/lib/numberWords";
import { unsavedStatus, type SaveStatus } from "@shell/lib/saveStatus";
import { countWords } from "@shell/lib/words";
import { Icon } from "@shell/ui/icons";
import { useState } from "react";

import { PromptBar } from "./PromptBar";
import { SceneEditor } from "./SceneEditor";
import type { Continuation, SceneEntry } from "./workspace";
import { sceneCodeNumbers, sceneTitle } from "./workspace";

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The shell's focus ring on every control the column offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The draft's disabled tool door — the geometry stays, the action waits. */
const DISABLED_DOOR =
  "flex cursor-not-allowed items-center gap-1 rounded border border-border/70 bg-surface-container-low/40 px-2.5 py-1 text-meta text-muted opacity-60";

/** The ribbon's neutral chapter-target pill — INTERIM Task 19: the read
 *  carries no chapter goal yet and the setter rides the book-settings
 *  surface (D20 places it inline at this element). */
function ChapterTargetPill() {
  const t = useTranslation();
  return (
    <div className="flex items-center gap-2 rounded-full border border-border bg-surface-container-low px-3 py-1 text-meta text-muted shadow-sm">
      <span>
        {t("writing.workspace.ribbon.chapterTarget")}{" "}
        <strong className="font-mono text-foreground">—</strong>
      </span>
      <div aria-hidden="true" className="h-1.5 w-16 overflow-hidden rounded-full bg-border">
        {/* No goal, no fill — the empty track is the honest neutral. */}
      </div>
      <button
        type="button"
        disabled
        title={t("writing.workspace.ribbon.targetEditNote")}
        aria-label={t("writing.workspace.ribbon.targetEdit")}
        className="cursor-not-allowed text-muted opacity-60"
      >
        <Icon name="write" size={12} />
      </button>
    </div>
  );
}

/** The ribbon — the draft's 44px bar: breadcrumb + code badge left (with
 *  KACHEL 9's amber unsaved pill while words are unsaved), the chapter-target
 *  pill center, the tool doors right. */
function Ribbon({ novel, entry, status }: { novel: Novel; entry: SceneEntry; status: SaveStatus }) {
  const t = useTranslation();
  const code = sceneCodeNumbers(entry);
  return (
    <div
      data-testid="workspace-ribbon"
      className="flex h-11 shrink-0 items-center justify-between gap-3 border-b border-border bg-panel px-5"
    >
      <div className="flex min-w-0 items-center gap-2 text-meta">
        <span className={`${SERIF} truncate text-muted`}>{novel.title}</span>
        <span aria-hidden="true" className="text-outline-variant">/</span>
        <span className="shrink-0 text-muted">
          {t("writing.workspace.tree.chapterLabel", { number: code.chapter })}
        </span>
        <span aria-hidden="true" className="text-outline-variant">/</span>
        <span className="shrink-0 font-medium text-foreground">
          {t("writing.workspace.tree.sceneWord", { number: code.scene })}
        </span>
        <span className="ml-1 shrink-0 rounded border border-border bg-surface-container-low px-1.5 py-0.5 font-mono text-[10px] text-muted">
          {t("writing.workspace.sceneCode", code)}
        </span>
        {/* KACHEL 9's warning pill — the amber mark while words exist only
            in the browser (the debounce, the wire, or a refused write). */}
        {unsavedStatus(status) && (
          // The amber identity rides the ink, dot and border; the fill is the
          // shell's warm surface, not a warning tint — warning ink on a tint
          // clears no AA bar at this size (the axe gate measures the live DOM).
          <span className="ml-1 inline-flex shrink-0 items-center gap-1.5 rounded-full border border-warning/40 bg-surface-container-low px-2 py-0.5 text-[10px] font-semibold text-warning">
            <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-warning" />
            {t("writing.workspace.ribbon.unsaved")}
          </span>
        )}
      </div>
      <ChapterTargetPill />
      <div className="flex shrink-0 items-center gap-1.5">
        {/* Fokus: INTERIM Task 18 — the zen wave owns the mode (D19's F9
            toggle lands with it); the door keeps its geometry and note. */}
        <button
          type="button"
          disabled
          title={t("writing.workspace.ribbon.focusNote")}
          className={DISABLED_DOOR}
        >
          <Icon name="focus" size={12} />
          <span>{t("writing.workspace.ribbon.focus")}</span>
        </button>
        {/* Verlauf: INTERIM #875 — the editing wave's revision-history
            surface; the light draft's honest note wins over the dark's
            per-scene availability claim. */}
        <button
          type="button"
          disabled
          title={t("writing.workspace.ribbon.historyNote")}
          className={DISABLED_DOOR}
        >
          <Icon name="clock" size={12} />
          <span>{t("writing.workspace.ribbon.history")}</span>
        </button>
        {/* Export: INTERIM #876 — the production wave's export studio;
            the novel-level ZIP stays the shelf quick menu's action. */}
        <button
          type="button"
          disabled
          title={t("writing.workspace.ribbon.exportNote")}
          className={DISABLED_DOOR}
        >
          <Icon name="export" size={12} />
          <span>{t("writing.workspace.ribbon.export")}</span>
        </button>
      </div>
    </div>
  );
}

/** The card foot's autosave face — one status, the draft's three voices.
 *  At rest the green „Automatisch gesichert"; engaged the amber „Sicherung
 *  läuft …"; refused KACHEL 9's red line with the retry that re-sends the
 *  body still held in the editor. The dot wears the state's tone. */
function SaveFoot({ status, onRetry }: { status: SaveStatus; onRetry: () => void }) {
  const t = useTranslation();
  if (status === "failed") {
    return (
      <div className="flex items-center gap-2 text-danger">
        <span className="text-[11px] font-medium">{t("writing.workspace.foot.failed")}</span>
        <button
          type="button"
          onClick={onRetry}
          className={`flex items-center gap-1 text-[11px] font-semibold underline underline-offset-2 hover:opacity-80 ${FOCUS}`}
        >
          <span>{t("writing.workspace.foot.retry")}</span>
          <Icon name="refresh" size={12} />
        </button>
      </div>
    );
  }
  // The engaged label keeps the foot's muted ink — warning ink on the paper
  // clears no AA bar at this size; the amber pulsing dot carries the state.
  return (
    <span className="text-[11px]">
      {t(status === "saving" ? "writing.workspace.foot.saving" : "writing.workspace.foot.saved")}
    </span>
  );
}

/** The paper card's scene face — the draft's anatomy, the row's own data,
 *  the live prose. Keyed per scene by the column: the word count resets with
 *  the document, the editor initializes once. */
function ScenePaper({
  novel,
  entry,
  status,
  onRetry,
  onBodyChange,
  continuation,
}: {
  novel: Novel;
  entry: SceneEntry;
  status: SaveStatus;
  onRetry: () => void;
  onBodyChange: (body: string) => void;
  continuation: Continuation;
}) {
  const t = useTranslation();
  const locale = activeLocale();
  const code = sceneCodeNumbers(entry);
  const title = sceneTitle(entry.scene.title, t("writing.workspace.untitledScene"));
  const overline = [entry.scene.setting, entry.scene.story_time]
    .filter((part): part is string => part != null && part.trim() !== "")
    .join(" · ");
  const runningHead =
    novel.author != null && novel.author.trim() !== ""
      ? `${novel.title} — ${novel.author}`
      : novel.title;
  // The foot's live count: the shared whitespace rule on the document as it
  // stands — moves with the writing, agrees with the server after a save.
  const [words, setWords] = useState(() => countWords(entry.scene.body));
  const failed = status === "failed";
  const dotTone = failed ? "bg-danger" : status === "saving" ? "bg-warning" : "bg-success";
  return (
    <article className="relative flex min-h-[780px] w-full max-w-[48rem] flex-col justify-between rounded-xl border border-border bg-panel p-12 shadow-card md:p-16">
      <div>
        {/* Running head — book — author (D22), italic, centered, no folio. */}
        <div
          data-testid="workspace-running-head"
          className={`${SERIF} mb-10 select-none border-b border-rule pb-4 text-center text-meta italic tracking-wide text-muted`}
        >
          {runningHead}
        </div>
        <div className="mb-8 space-y-2 text-center">
          {/* The written-out ordinals (the number-words util, bound 20,
              digit fallback) — the draft's tracked terracotta eyebrow. */}
          <div className="text-[11px] font-bold uppercase tracking-[0.22em] text-primary">
            {t("writing.workspace.header.eyebrow", {
              chapter: capitalizedWord(code.chapter, locale),
              scene: capitalizedWord(code.scene, locale),
            })}
          </div>
          <h1 className={`${SERIF} text-3xl font-normal tracking-tight text-foreground md:text-4xl`}>
            {title}
          </h1>
          {overline !== "" && (
            <div data-testid="workspace-overline" className="text-meta text-muted">
              {overline}
            </div>
          )}
          <div aria-hidden="true" className="flex items-center justify-center pt-2">
            <span className="h-px w-12 bg-primary/40" />
          </div>
        </div>
        {/* The prose — the active scene's body, editable through TipTap.
            The drop cap and editorial face ride globals.css, inherited from
            the read-only port unchanged. */}
        <div data-testid="workspace-prose">
          <SceneEditor
            body={entry.scene.body}
            label={t("writing.workspace.editor.proseLabel")}
            continuation={continuation}
            onChange={(body) => {
              setWords(countWords(body));
              onBodyChange(body);
            }}
          />
        </div>
      </div>
      {/* The card foot — the scene's own live count and the autosave face
          (one status owner with the topbar and the rail). KACHEL 9's failure
          tints the whole foot; the dot pulses while engaged or refused. */}
      <footer
        className={`mt-14 flex select-none items-center justify-between border-t pt-4 text-meta ${
          failed ? "border-danger/30 bg-danger/10 text-danger" : "border-rule text-muted"
        }`}
      >
        <div className="flex items-center gap-2">
          <span
            aria-hidden="true"
            className={`h-2 w-2 rounded-full ${dotTone} ${status === "saving" || failed ? "animate-pulse" : ""}`}
          />
          <span>{t("writing.workspace.foot.words", { count: words })}</span>
        </div>
        <SaveFoot status={status} onRetry={onRetry} />
      </footer>
    </article>
  );
}

export function EditorColumn({
  novel,
  entry,
  emptyChapter,
  status,
  onRetry,
  onBodyChange,
  onCreateScene,
  continuation,
}: {
  novel: Novel;
  /** The active scene — null on the empty faces. */
  entry: SceneEntry | null;
  /** Chapters stand but the active one holds no scene (D16's real state). */
  emptyChapter: boolean;
  /** The one save-status owner's state (the page's autosave). */
  status: SaveStatus;
  /** Re-send the refused body (KACHEL 9's Wiederholen). */
  onRetry: () => void;
  /** Every prose edit, handed to the page's autosave debounce. */
  onBodyChange: (body: string) => void;
  /** Kachel 4's first-scene door — the page creates under the empty
   *  chapter and selects the new scene (D16's canonical flow). */
  onCreateScene: () => void;
  /** The continuation's state (the page's hook) — the ghost layer and the
   *  prompt bar ride it; the empty faces carry neither. */
  continuation: Continuation;
}) {
  const t = useTranslation();
  return (
    <section
      aria-label={t("writing.workspace.editor.label")}
      className="relative flex h-full min-w-0 flex-1 flex-col overflow-hidden bg-surface-container-low"
    >
      {entry !== null && <Ribbon novel={novel} entry={entry} status={status} />}
      {/* The scrolling stage — tabIndex gives the scroll region keyboard
          access (axe scrollable-region-focusable); the prose itself is a
          focusable textbox now, the shell main's own pattern. The bottom
          padding clears the floating prompt bar when a scene stands, so
          the card foot stays reachable behind it. */}
      <div
        tabIndex={0}
        className={`flex flex-1 justify-center overflow-y-auto px-6 pt-7 ${entry !== null ? "pb-36" : "pb-16"}`}
      >
        {entry !== null ? (
          <ScenePaper
            key={entry.scene.id}
            novel={novel}
            entry={entry}
            status={status}
            onRetry={onRetry}
            onBodyChange={onBodyChange}
            continuation={continuation}
          />
        ) : emptyChapter ? (
          /* Kachel 4 — the empty chapter: the scene explained, the
             first-scene door live (D16's canonical new-chapter flow). */
          <div className="flex w-full max-w-[48rem] flex-col items-center justify-center rounded-xl border border-border bg-panel p-8 text-center shadow-card">
            <span className="mb-1 text-primary/70">
              <Icon name="write" size={28} />
            </span>
            <h1 className={`${SERIF} text-emph font-semibold text-foreground`}>
              {t("writing.workspace.emptyChapter.title")}
            </h1>
            <p className="mt-1 max-w-xs text-meta leading-snug text-muted">
              {t("writing.workspace.emptyChapter.body")}
            </p>
            <button
              type="button"
              onClick={onCreateScene}
              className={`mt-3 flex items-center gap-1 rounded bg-primary px-3 py-1.5 text-meta font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS}`}
            >
              <Icon name="plus" size={13} />
              <span>{t("writing.workspace.emptyChapter.action")}</span>
            </button>
          </div>
        ) : (
          /* Kachel 3 — the empty book: the open-book mark, the contemplative
             invitation. The explorer's invitation card carries the create
             door (live — the first chapter opens on Kachel 4). */
          <div className="flex w-full max-w-[48rem] flex-col items-center justify-center rounded-xl border border-border bg-panel p-8 text-center shadow-card">
            <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-full border border-border bg-surface-container-low text-primary">
              <Icon name="autoStories" size={24} />
            </div>
            <h1 className={`${SERIF} text-emph font-semibold text-foreground`}>
              {t("writing.workspace.emptyBook.editorTitle")}
            </h1>
            <p className="mt-1 max-w-[220px] text-meta leading-relaxed text-muted">
              {t("writing.workspace.emptyBook.editorBody")}
            </p>
          </div>
        )}
      </div>
      {/* The floating prompt bar (Task 16) — the draft's pill over the
          stage's foot, real prompts on the continue endpoint (D5). Only
          the scene face carries it: no scene, nothing to continue. */}
      {entry !== null && <PromptBar continuation={continuation} />}
    </section>
  );
}
