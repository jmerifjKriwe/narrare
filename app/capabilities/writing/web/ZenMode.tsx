/**
 * The zen mode (W4 Task 18) — the round's harmonized zen authority
 * (`zen-focus-2`, light face wins; the dark rides the tokens' light-dark
 * pairs). F9 clears the desk (D19): the page SWAPS the workspace's columns
 * for this room while zen stands — the columns unmount, they are not hidden
 * beneath it (one live editor at a time; two would double the ghost's
 * keyboard contract). The swap IS the design: entry and exit flush the
 * autosave first and let the scene cache catch up, so each face's editor
 * initializes on the saved truth. The scene's prose stands centered under
 * the manuscript head, and the room's own chrome replaces the app's — the
 * exit chip, the counters and the pomodoro above, the focus presets below.
 * The page owns the toggle and the flush-first leave; this component is
 * the room itself.
 *
 * What is REAL (D6, frontend-real): the Absatz-/Satz-/Normal dimming (the
 * editor's decoration plugin, the mode rides the segment control), the
 * pomodoro (session-only — no storage, no server row; its lifetime is the
 * zen spell, design §12), and the counters — today reads the activity
 * aggregate the page hands over (the ring's own source, neutral „—" when
 * the aggregate is unavailable), the session counts the live net delta
 * since entry (the shared whitespace rule). The scene overline is the
 * row's own setting · story_time, never the draft's mock line.
 *
 * What is CUT or DISABLED: NO sepia control ships (D18 — the round
 * regenerated the draft without one, „STRIKT: KEIN Sepia-Button"); the
 * soundscape keeps its geometry disabled with the lock and the drafted
 * note (INTERIM #877, gap row 12 — the audio wave owns the trigger).
 *
 * The ghost stays reachable (PR 4's seam is not stranded): the prompt bar
 * floats above the control pill — the draft draws no bar of its own in
 * zen, the brief's „ghost reachable" owns the extension — and the
 * continuation's faces render at the prose tail exactly as in the
 * workspace (the page's one hook, the editor's one keyboard contract:
 * Tab accepts, Esc dismisses BEFORE the room's own Esc).
 *
 * The room is modal weight: a fixed surface over the app chrome (the rail
 * and topbar stay mounted beneath it, covered and out of reach), a focus
 * trap that keeps Tab inside (the LeaveGuard's own discipline), and the
 * page's Esc handler defers to the ghost and the guard before it closes
 * the room. Every exit — healthy or the guard's discard — returns the
 * focus to the ribbon door that opened the room (the page's one restore).
 * The decorative spines and the end mark are the draft's own, aria-hidden;
 * the fullscreen toggle asks the browser (the draft's control), the first
 * Esc in fullscreen belongs to the browser.
 */
import { useEffect, useRef, useState } from "react";

import type { Novel } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { Icon } from "@shell/ui/icons";

import { todayState } from "./activity";
import { PromptBar } from "./PromptBar";
import { SceneEditor } from "./SceneEditor";
import {
  formatClock,
  sceneCodeNumbers,
  sceneTitle,
  useSessionWords,
  useZenTimer,
  type Continuation,
  type SceneEntry,
  type ZenFocusMode,
} from "./workspace";

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The shell's focus ring on every control the room offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The trap's stop list — the LeaveGuard's own, plus the prose textbox
 *  (contenteditable), so the wrap reads the room's real seats. */
const FOCUSABLE =
  'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex="-1"]), [contenteditable="true"]';

/** The three presets in the draft's segment order. */
const PRESETS: ReadonlyArray<{ mode: ZenFocusMode; key: "writing.workspace.zen.focus.paragraph" | "writing.workspace.zen.focus.sentence" | "writing.workspace.zen.focus.normal" }> = [
  { mode: "paragraph", key: "writing.workspace.zen.focus.paragraph" },
  { mode: "sentence", key: "writing.workspace.zen.focus.sentence" },
  { mode: "normal", key: "writing.workspace.zen.focus.normal" },
];

export function ZenMode({
  novel,
  entry,
  todayWords,
  continuation,
  onBodyChange,
  onExit,
}: {
  novel: Novel;
  /** The active scene — the room's prose, overline and chapter head. */
  entry: SceneEntry;
  /** Today's net words from the activity aggregate (the page's read);
   *  null when the aggregate is unavailable — the neutral, never a guess. */
  todayWords: number | null;
  /** The page's one continuation — the ghost's faces and the bar's ask. */
  continuation: Continuation;
  /** Every prose edit, handed to the page's autosave (the one write path). */
  onBodyChange: (body: string) => void;
  /** The exit chip's leave — the page flushes first (the leave guard's rule). */
  onExit: () => void;
}) {
  const t = useTranslation();
  const roomRef = useRef<HTMLDivElement>(null);
  // Absatz-Fokus is the entry mode — the draft's segment draws it chosen.
  const [focus, setFocus] = useState<ZenFocusMode>("paragraph");
  const timer = useZenTimer();
  const session = useSessionWords(entry.scene.body);

  const code = sceneCodeNumbers(entry);
  const chapterTitle = sceneTitle(entry.chapter.title, t("writing.workspace.untitledChapter"));
  const overline = [entry.scene.setting, entry.scene.story_time]
    .filter((part): part is string => part != null && part.trim() !== "")
    .join(" · ");
  const todayVoice = todayWords === null ? "unavailable" : todayState(todayWords);

  // The session's edits: the delta counter tracks every body, then the
  // page's one write path carries it (the autosave, the ghost dismissal).
  function handleBodyChange(body: string) {
    session.track(body);
    onBodyChange(body);
  }

  // --- The fullscreen toggle (the draft's control) -------------------------
  const [fullscreen, setFullscreen] = useState(false);
  useEffect(() => {
    function onChange() {
      setFullscreen(Boolean(document.fullscreenElement));
    }
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);
  function toggleFullscreen() {
    if (document.fullscreenElement) {
      void document.exitFullscreen?.().catch(() => {});
    } else {
      void document.documentElement.requestFullscreen?.().catch(() => {});
    }
  }

  // --- The room's focus trap ------------------------------------------------
  // Tab wraps inside the surface at both ends — the covered chrome keeps
  // no focus seat while the room stands (the LeaveGuard's own discipline).
  // Esc is NOT here: the page owns it, after the ghost and the guard.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Tab") return;
      const room = roomRef.current;
      if (room === null) return;
      const nodes = Array.from(room.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (nodes.length === 0) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      const active = document.activeElement;
      if (event.shiftKey) {
        if (active === first || !room.contains(active)) {
          event.preventDefault();
          last.focus();
        }
      } else if (active === last || !room.contains(active)) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  // --- The pomodoro's end, spoken once --------------------------------------
  // The hidden region stands empty from mount and fills AT the done
  // transition (the ghost arrival's own pattern: a live region speaks
  // changes, never initial content).
  const [timerDone, setTimerDone] = useState("");
  const prevDone = useRef(false);
  useEffect(() => {
    if (timer.done && !prevDone.current) setTimerDone(t("writing.workspace.zen.timer.done"));
    else if (!timer.done) setTimerDone("");
    prevDone.current = timer.done;
  }, [timer.done, t]);

  return (
    <div
      ref={roomRef}
      role="dialog"
      aria-modal="true"
      aria-label={t("writing.workspace.zen.label")}
      data-testid="zen-mode"
      className="fixed inset-0 z-50 overflow-y-auto bg-background text-foreground"
    >
      {/* The decorative spines — the draft's own „NARRARE · ZEN", never a
          story-specific decoration (gap row 15's removal stands). */}
      <aside
        aria-hidden="true"
        className="pointer-events-none fixed inset-y-0 left-0 z-10 flex w-8 select-none items-center justify-center"
      >
        {/* The draft's spine ink is muted/40 (zen-focus-2.html:174/179) — below
            the AA floor (1.7:1). The fidelity gate rides it at full muted
            (4.8:1 light / 5.1:1 dark), the PR4 ghost-ink discipline: geometry
            kept, floor measured. The dim itself is the room's one sanctioned
            below-AA exemption; the decoration is not. */}
        <div className="rotate-180 whitespace-nowrap text-eyebrow uppercase tracking-[0.24em] text-muted [writing-mode:vertical-rl]">
          {t("writing.workspace.zen.spine")}
        </div>
      </aside>
      <aside
        aria-hidden="true"
        className="pointer-events-none fixed inset-y-0 right-0 z-10 flex w-8 select-none items-center justify-center"
      >
        <div className="whitespace-nowrap text-eyebrow uppercase tracking-[0.24em] text-muted [writing-mode:vertical-rl]">
          {t("writing.workspace.zen.spine")}
        </div>
      </aside>

      {/* The floating status bar — the exit chip left, the counters and the
          pomodoro right. Pointer-transparent between the controls. */}
      <header className="pointer-events-none fixed inset-x-0 top-0 z-30 flex items-center justify-between px-6 py-4">
        <div className="pointer-events-auto">
          <button
            type="button"
            onClick={onExit}
            aria-label={t("writing.workspace.zen.exit")}
            aria-keyshortcuts="Escape"
            className={`group flex items-center gap-2 rounded-lg border border-border/70 bg-card/80 px-3 py-1.5 text-meta text-muted shadow-sm backdrop-blur-md transition-all hover:bg-card hover:text-foreground ${FOCUS}`}
          >
            <Icon name="arrowLeft" size={15} />
            <span>{t("writing.workspace.zen.exit")}</span>
            <kbd className="ml-1 rounded border border-border bg-soft/80 px-1.5 py-0.5 font-mono text-[10px] text-muted/80">
              Esc
            </kbd>
          </button>
        </div>
        <div className="pointer-events-auto flex items-center gap-3">
          {/* The counters — today the aggregate's net (neutral when
              unavailable), the session the live delta since entry. */}
          <div className="flex items-center gap-1.5 rounded-lg border border-border/60 bg-card/70 px-3 py-1.5 text-meta tabular-nums text-muted shadow-sm backdrop-blur-md">
            {t("writing.workspace.zen.counters", {
              state: todayVoice,
              count: todayWords ?? 0,
              session: session.words,
            })}
          </div>
          {/* The pomodoro — session-only (design §12): pause/resume as
              drafted, the reset the design's start/pause/reset contract
              (§6.5) names; the round draws no reset key of its own. */}
          <div
            role="group"
            aria-label={t("writing.workspace.zen.timer.label")}
            className="flex items-center gap-2 rounded-lg border border-border/60 bg-card/70 px-2.5 py-1.5 shadow-sm backdrop-blur-md"
          >
            <button
              type="button"
              onClick={timer.toggle}
              aria-label={t(timer.running ? "writing.workspace.zen.timer.pause" : "writing.workspace.zen.timer.resume")}
              className={`flex h-5 w-5 items-center justify-center rounded-full bg-secondary-container/60 text-primary transition-colors hover:bg-secondary-container ${FOCUS}`}
            >
              <Icon name={timer.running ? "pause" : "play"} size={12} />
            </button>
            <span className="text-meta font-medium tabular-nums tracking-tight text-foreground">
              {formatClock(timer.remaining)}
            </span>
            <button
              type="button"
              onClick={timer.reset}
              aria-label={t("writing.workspace.zen.timer.reset")}
              className={`flex h-5 w-5 items-center justify-center rounded-full text-muted transition-colors hover:text-foreground ${FOCUS}`}
            >
              <Icon name="refresh" size={12} />
            </button>
          </div>
        </div>
      </header>

      {/* The centered scene corpus — the manuscript head, the live prose
          under the focus dimming, the ghost at the tail, the end mark. The
          bottom padding clears BOTH floating bars (the prompt bar rides one
          step above the control pill). */}
      <div className="flex min-h-full flex-col items-center justify-center px-6 pb-48 pt-24">
        <article className="w-full max-w-[36rem]">
          <header className="mb-10 select-none text-center">
            {/* The draft's eyebrow is muted/80 (zen-focus-2.html:222, 3.3:1) —
                the gate rides full muted so the book's own name clears AA. */}
            <div className="mb-2 text-eyebrow uppercase tracking-[0.16em] text-muted">
              {t("writing.workspace.zen.eyebrow", { title: novel.title })}
            </div>
            <h1 className={`${SERIF} text-[2rem] font-medium leading-[1.2] tracking-tight text-primary`}>
              {t("writing.workspace.tree.chapterName", { number: code.chapter, title: chapterTitle })}
            </h1>
            {overline !== "" && (
              <p data-testid="zen-overline" className={`${SERIF} mt-2 text-body italic text-muted`}>
                {overline}
              </p>
            )}
            {/* The draft's divider ink is muted/40 (zen-focus-2.html:228) — the
                gate rides full muted (the spine's discipline, same floor). */}
            <div aria-hidden="true" className="mt-6 flex items-center justify-center gap-3 text-muted">
              <span className="h-px w-10 bg-border" />
              <span className="text-[10px] uppercase tracking-[0.2em]">
                {t("writing.workspace.zen.focusDivider")}
              </span>
              <span className="h-px w-10 bg-border" />
            </div>
          </header>
          {/* The prose — the same live editor the workspace rides, keyed by
              the page's selection; the zen face (no drop cap, the draft's
              indent) and the dimming ride globals.css's .zen-prose rules. */}
          <div className="zen-prose" data-testid="zen-prose">
            <SceneEditor
              body={entry.scene.body}
              label={t("writing.workspace.editor.proseLabel")}
              continuation={continuation}
              focus={focus}
              autoFocus
              onChange={handleBodyChange}
            />
          </div>
          {/* The draft's end mark is muted/45 (zen-focus-2.html:265, 1.8:1) —
              the gate rides full muted (the spine's discipline, same floor). */}
          <div aria-hidden="true" className="mt-14 select-none text-center">
            <span className={`${SERIF} pl-2 text-lg font-medium tracking-[0.6em] text-muted`}>§ § §</span>
          </div>
        </article>
      </div>

      {/* The prompt bar — PR 4's seam reachable inside the room (the brief's
          own extension; the draft draws no zen bar). It floats above the
          control pill, the workspace's own geometry one step up. */}
      <div className="pointer-events-none fixed inset-x-0 bottom-16 z-30">
        <PromptBar continuation={continuation} />
      </div>

      {/* The floating control pill — the focus presets, the disabled
          soundscape (INTERIM #877), the fullscreen toggle. NO sepia (D18). */}
      <footer className="fixed bottom-6 left-1/2 z-30 -translate-x-1/2 select-none">
        <div className="flex items-center gap-2 rounded-full border border-border/80 bg-card/90 p-1.5 shadow-overlay backdrop-blur-md">
          <div
            role="group"
            aria-label={t("writing.workspace.zen.focus.label")}
            className="flex items-center gap-1 rounded-full bg-soft/80 p-0.5"
          >
            {PRESETS.map((preset) => (
              <button
                key={preset.mode}
                type="button"
                onClick={() => setFocus(preset.mode)}
                aria-pressed={focus === preset.mode}
                className={`rounded-full px-3 py-1 text-meta transition-all ${FOCUS} ${
                  focus === preset.mode
                    ? "border border-border/50 bg-card font-semibold text-primary shadow-sm"
                    : "zen-preset-idle font-medium hover:text-foreground"
                }`}
              >
                {t(preset.key)}
              </button>
            ))}
          </div>
          <div aria-hidden="true" className="mx-0.5 h-4 w-px bg-border" />
          {/* Soundscape: INTERIM #877 — the audio wave's assets + playback;
              the geometry stays, disabled with the lock and the drafted
              note (gap row 12, both faces). */}
          <button
            type="button"
            disabled
            aria-label={t("writing.workspace.zen.soundscape")}
            title={t("writing.workspace.zen.soundscapeNote")}
            className="flex h-8 w-8 cursor-not-allowed items-center justify-center gap-0.5 rounded-full text-muted/60"
          >
            <Icon name="soundOff" size={15} />
            <Icon name="lock" size={10} />
          </button>
          <div aria-hidden="true" className="mx-0.5 h-4 w-px bg-border" />
          <button
            type="button"
            onClick={toggleFullscreen}
            aria-label={t(fullscreen ? "writing.workspace.zen.fullscreenExit" : "writing.workspace.zen.fullscreen")}
            className={`flex h-8 w-8 items-center justify-center rounded-full text-muted transition-all hover:bg-soft hover:text-foreground ${FOCUS}`}
          >
            <Icon name={fullscreen ? "fullscreenExit" : "fullscreen"} size={16} />
          </button>
        </div>
      </footer>

      {/* The pomodoro's end, spoken once at the transition. */}
      <p role="status" className="sr-only">
        {timerDone}
      </p>
    </div>
  );
}