/**
 * The editor column (W4 Task 11, read-only) — the scene-centric draft's
 * paper stage on the shell's tokens: the 44px ribbon (breadcrumb + the
 * derived scene-code badge, the chapter-target pill, the tool doors), the
 * scrolling stage with the paper card (max-w 48rem), and the card's own
 * anatomy: running head, chapter/scene eyebrow, title, overline, sepia
 * rule, drop-cap prose, foot.
 *
 * Honest readings of the draft (the gap doc records them):
 * - The running head is `novel.author` beside the book (D22) — the book
 *   alone when no author stands. NO folio, NO page count (row 9 — the
 *   light draft pins „KEIN Folio, KEINE Seitenzahl").
 * - The chapter-target pill keeps the neutral „—": ChapterRead carries no
 *   target yet, and the setter is Task 19's (D20 places it inline here).
 *   Fokus waits for the zen wave (Task 18), Verlauf for the editing wave
 *   (INTERIM #875), Export for the production wave (INTERIM #876) — each
 *   disabled with the light draft's own note, never a pretend door.
 * - The foot's autosave line is the INTERIM static (Task 12 wires the
 *   live owner): „Automatisch gesichert" without a timestamp — a „vor
 *   1 Min." claim would name a save nothing performed yet. The pulse dot
 *   is the drafted autosave/word-count mark (row 6), not a causality pill.
 * - Ghost text and the prompt bar are PR 4's (Tasks 16/17) — the prose
 *   ends where the scene's own words end.
 * - The prose is the scene body's paragraphs, read-only: Task 12 brings
 *   TipTap and the editing surface. The drop cap is the draft's
 *   first-letter float (globals.css, the tokens' primary).
 *
 * The empty faces answer per `workspace-states` (Kacheln 3/4): the
 * unwritten work and the first-scene invitation, their create doors
 * disabled until Task 13 wires the CRUD.
 */

import type { Novel } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { activeLocale } from "@shell/lib/locale";
import { capitalizedWord } from "@shell/lib/numberWords";
import { Icon } from "@shell/ui/icons";

import type { SceneEntry } from "./workspace";
import { sceneCodeNumbers, sceneTitle } from "./workspace";

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The shell's focus ring on every control the column offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The draft's disabled tool door — the geometry stays, the action waits. */
const DISABLED_DOOR =
  "flex cursor-not-allowed items-center gap-1 rounded border border-border/70 bg-surface-container-low/40 px-2.5 py-1 text-meta text-muted opacity-60";

/** The body's paragraphs: blank lines separate, single newlines stay inside
 *  the paragraph (whitespace-pre-line). Empty prose renders no paragraph —
 *  the paper stays honest, never an invented sentence. */
function paragraphs(body: string): string[] {
  return body
    .split(/\n[ \t]*\n/)
    .map((paragraph) => paragraph.trim())
    .filter((paragraph) => paragraph !== "");
}

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

/** The ribbon — the draft's 44px bar: breadcrumb + code badge left, the
 *  chapter-target pill center, the tool doors right. */
function Ribbon({ novel, entry }: { novel: Novel; entry: SceneEntry }) {
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

/** The paper card's scene face — the draft's anatomy, the row's own data. */
function ScenePaper({ novel, entry }: { novel: Novel; entry: SceneEntry }) {
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
          {overline !== "" && <div className="text-meta text-muted">{overline}</div>}
          <div aria-hidden="true" className="flex items-center justify-center pt-2">
            <span className="h-px w-12 bg-primary/40" />
          </div>
        </div>
        {/* The prose — EB Garamond, the draft's 1.85 leading, drop cap on
            the first paragraph. Read-only until Task 12's editor. */}
        <div
          data-testid="workspace-prose"
          className={`${SERIF} space-y-6 text-[1.18rem] leading-[1.85] text-foreground/95 md:text-[1.22rem]`}
        >
          {paragraphs(entry.scene.body).map((paragraph, at) => (
            <p
              key={at}
              className={`whitespace-pre-line text-justify ${at === 0 ? "workspace-drop-cap" : ""}`}
            >
              {paragraph}
            </p>
          ))}
        </div>
      </div>
      {/* The card foot — the scene's own count and the INTERIM autosave
          line (Task 12 wires the live owner; no timestamp claim before it).
          The pulse dot is the drafted mark (row 6), never a causality pill. */}
      <footer className="mt-14 flex select-none items-center justify-between border-t border-rule pt-4 text-meta text-muted">
        <div className="flex items-center gap-2">
          <span aria-hidden="true" className="h-2 w-2 animate-pulse rounded-full bg-sync-badge-ink" />
          <span>{t("writing.workspace.foot.words", { count: entry.scene.word_count })}</span>
        </div>
        <span className="text-[11px]">{t("writing.workspace.foot.saved")}</span>
      </footer>
    </article>
  );
}

export function EditorColumn({
  novel,
  entry,
  emptyChapter,
}: {
  novel: Novel;
  /** The active scene — null on the empty faces. */
  entry: SceneEntry | null;
  /** Chapters stand but the active one holds no scene (D16's real state). */
  emptyChapter: boolean;
}) {
  const t = useTranslation();
  return (
    <section
      aria-label={t("writing.workspace.editor.label")}
      className="flex h-full min-w-0 flex-1 flex-col overflow-hidden bg-surface-container-low"
    >
      {entry !== null && <Ribbon novel={novel} entry={entry} />}
      {/* The scrolling stage — tabIndex gives the scroll region keyboard
          access (axe scrollable-region-focusable): the read-only prose has
          no focusable content of its own until Task 12's editor lands; the
          shell's main landmark uses the same pattern. */}
      <div tabIndex={0} className="flex flex-1 justify-center overflow-y-auto px-6 pb-16 pt-7">
        {entry !== null ? (
          <ScenePaper novel={novel} entry={entry} />
        ) : emptyChapter ? (
          /* Kachel 4 — the empty chapter: the scene explained, the create
             door disabled until Task 13 wires the CRUD. */
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
              disabled
              title={t("writing.workspace.crudNote")}
              className={`mt-3 flex cursor-not-allowed items-center gap-1 rounded bg-primary px-3 py-1.5 text-meta font-medium text-primary-foreground opacity-50 shadow-sm ${FOCUS}`}
            >
              <Icon name="plus" size={13} />
              <span>{t("writing.workspace.emptyChapter.action")}</span>
            </button>
          </div>
        ) : (
          /* Kachel 3 — the empty book: the open-book mark, the contemplative
             invitation. The explorer's invitation card carries the create
             door (also disabled until Task 13). */
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
    </section>
  );
}
