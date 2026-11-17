/**
 * The scene editor (W4 Task 12) — the TipTap surface that replaces the
 * read-only prose. The scene body is PLAIN PROSE, not Markdown: paragraphs
 * joined by a blank line, hard breaks by a single newline — the same shape
 * the read-only port drew (`paragraphs` split on blank lines) and the
 * server's one whitespace rule counts. The demo corpus, the continuation
 * stream and the interchange import all write that shape; a Markdown
 * serializer would escape the prose's own dashes and quotes and drift from
 * the count, so the editor speaks plain text in both directions.
 *
 * The extension set is the StarterKit pared to prose: document, paragraph,
 * text, hard break and undo/redo. No headings, lists, marks or code — the
 * scene-centric draft draws paragraphs only, and a formatting shortcut that
 * created a node the storage cannot carry would be a false affordance.
 *
 * Content initializes once per scene (`bodyToHtml`); the page keys this
 * component by scene id, so a switch remounts with the new body and a save's
 * cache refetch never resets a live caret. Every edit emits the whole body
 * as plain text through `onChange` — the page's autosave owns the wire.
 *
 * The editable element is a real labelled textbox: @tiptap/core injects
 * role="textbox" in createView, but the React binding re-props the view from
 * the raw editorProps, so the explicit role/aria-multiline/aria-label keep
 * the name valid (axe computes „generic" for the roleless div and flags
 * aria-prohibited-attr while the editor is empty — the MarkdownEditor's own
 * lesson). The drop cap and the editorial face ride globals.css's
 * `.workspace-prose-live` rules, the read-only mark inherited unchanged.
 *
 * The ghost layer (W4 Task 16, design G4): the continuation's proposal
 * stands at the scene tail, NEVER inside the document — the textbox holds
 * the scene's own words until Tab accepts. Three faces: KACHEL 7's
 * streaming chrome (the pulsing „ARIA schreibt …" chip, the block cursor),
 * the light draft's pending preview (italic, the writing area's ink, the
 * [Tab] keycap pill) and KACHEL 8's corrected error face (the Grund chip,
 * the calm title, the reassurance, Erneut versuchen / Verwerfen). The
 * keyboard contract is the ghost's own: Tab accepts from the prose, Esc
 * dismisses in the CAPTURE phase — before the leave guard's bubble-phase
 * Esc, so a standing ghost is dropped first and the guard keeps its ask.
 * The proposal's arrival is spoken once, AT the streaming→pending
 * transition, through a visually-hidden live region: a live region
 * announces changes, never its initial content, so the region stands
 * empty until the draft lands — the preview itself wears no role.
 * Acceptance inserts the proposal as new paragraph(s) at the tail and emits
 * the joined body through onChange: the autosave chain owns the write (and
 * its invalidation family), exactly as a typed edit does.
 *
 * The draft's area-writing/70 ink fails the axe AA floor on both themes
 * (~3.2:1 light, ~3.9:1 dark on the paper); the ink rides full strength
 * (6.1:1 / 6.6:1) and the /5 wash carries the softness — the amber pill's
 * own discipline (Task 12): the identity stays, the floor is kept.
 */
import { EditorContent, useEditor } from "@tiptap/react";
import type { Editor } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import { useCallback, useEffect, useRef, useState } from "react";

import { useTranslation } from "@shell/lib/i18n";
import { Icon } from "@shell/ui/icons";

import type { Continuation } from "./workspace";

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The shell's focus ring on the ghost's one control. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The proposal's editorial face — the prose's own scale and leading, the
 *  italic voice the draft draws, the writing area's ink at full strength
 *  (the AA floor; the docblock above carries the measured reason). */
const GHOST_PROSE = `${SERIF} text-[1.18rem] italic leading-[1.85] text-area-writing md:text-[1.22rem]`;

/** Prose only: the StarterKit with every non-prose node and mark disabled.
 *  One identity for the component's life — a fresh array per render would
 *  rebuild the editor. Document, paragraph, text, hardBreak and undoRedo
 *  stay; the draft draws no heading, list, quote, rule or formatting. */
const PROSE_EXTENSIONS = [
  StarterKit.configure({
    blockquote: false,
    bold: false,
    bulletList: false,
    code: false,
    codeBlock: false,
    dropcursor: false,
    gapcursor: false,
    heading: false,
    horizontalRule: false,
    italic: false,
    listItem: false,
    listKeymap: false,
    link: false,
    orderedList: false,
    strike: false,
    trailingNode: false,
    underline: false,
  }),
];

function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/**
 * The plain body as the HTML the editor initializes from: blank lines
 * separate paragraphs (the read-only port's own split), single newlines
 * become hard breaks, the markup characters prose may carry are escaped.
 * An empty or whitespace-only body is one empty paragraph — the paper stays
 * honest, never an invented sentence. Trimming each block mirrors the
 * read-only rendering, so the first non-empty paragraph wears the drop cap.
 */
export function bodyToHtml(body: string): string {
  const blocks = body
    .split(/\n[ \t]*\n/)
    .map((block) => block.trim())
    .filter((block) => block !== "");
  if (blocks.length === 0) return "<p></p>";
  return blocks
    // escapeHtml below escapes every block; concatenation (not an HTML template literal) keeps the "Avoid HTML in Template Strings" rule quiet.
    .map((block) => "<p>" + block.split("\n").map(escapeHtml).join("<br>") + "</p>")
    .join("");
}

/** KACHEL 7 — the streaming face: the pulsing ARIA chip over the growing
 *  preview, the block cursor at the wire's edge. The chip is the live
 *  announcement (once, when the stream starts); the preview itself is not
 *  a live region — a delta-by-delta readout would spam the reader. */
function GhostStreaming({ text }: { text: string }) {
  const t = useTranslation();
  return (
    <div
      data-testid="ghost-preview"
      className="mt-6 rounded-lg border border-area-writing/30 bg-area-writing/5 p-3.5"
    >
      <div
        role="status"
        className="mb-1.5 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-area-writing"
      >
        <span aria-hidden="true" className="h-1.5 w-1.5 animate-pulse rounded-full bg-area-writing" />
        {t("writing.workspace.ghost.writing")}
      </div>
      <p className={GHOST_PROSE}>
        {text}
        <span aria-hidden="true" className="ml-0.5 inline-block h-3.5 w-1.5 animate-pulse bg-area-writing align-middle" />
      </p>
    </div>
  );
}

/** The light draft's pending face — the italic preview at the tail with
 *  the [Tab] keycap pill inline after it. The pill is a real button (the
 *  dark face draws it as one): pointer users accept by click, the keyboard
 *  by Tab from the prose or Enter on the pill itself. The preview is NOT a
 *  live region — a span mounted populated never speaks; the arrival is
 *  announced by the editor's hidden region at the transition instead. */
function GhostPending({ text, onAccept }: { text: string; onAccept: () => void }) {
  const t = useTranslation();
  return (
    <div data-testid="ghost-preview" className="mt-6">
      <p className={`${GHOST_PROSE} text-justify`}>
        <span className="rounded bg-area-writing/5 px-1 py-0.5">
          {text}
        </span>
        <button
          type="button"
          onClick={onAccept}
          aria-keyshortcuts="Tab"
          className={`ml-2 inline-flex items-center gap-1.5 rounded-full bg-primary px-2 py-0.5 align-middle font-sans text-[11px] font-medium not-italic text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS}`}
        >
          <kbd className="rounded border border-primary-foreground/40 px-1 font-mono text-[10px]">Tab</kbd>
          <span>{t("writing.workspace.ghost.accept")}</span>
        </button>
      </p>
    </div>
  );
}

/** KACHEL 8 — the corrected error face (the round-2 authority, verbatim
 *  tri-catalog): the Grund chip, the calm title, the reassurance that the
 *  scene's own words stand untouched, and the two doors — Erneut versuchen
 *  re-runs the very ask, Verwerfen clears the face. No blocking dialog.
 *  The body's muted ink rides the panel, not the draft's red wash: the
 *  wash fails the AA floor for small text in the dark half (the amber
 *  pill's discipline again — the identity rides the ink and the border). */
function GhostError({ onRetry, onDismiss }: { onRetry: () => void; onDismiss: () => void }) {
  const t = useTranslation();
  return (
    <div
      role="alert"
      data-testid="ghost-error"
      className="mt-6 space-y-2 rounded-md border border-danger/40 bg-panel p-3 text-left"
    >
      <span className="inline-flex items-center gap-1.5 rounded-full border border-danger/40 bg-surface-container-low px-2 py-0.5 text-[10px] font-semibold text-danger">
        <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-danger" />
        {t("writing.workspace.ghost.errorChip")}
      </span>
      <div className="flex items-center gap-1.5 text-xs font-semibold text-danger">
        <Icon name="warning" size={15} />
        <span>{t("writing.workspace.ghost.errorTitle")}</span>
      </div>
      <p className="text-[11px] leading-relaxed text-muted">{t("writing.workspace.ghost.errorBody")}</p>
      <div className="flex items-center gap-2 pt-1 font-sans">
        <button
          type="button"
          onClick={onRetry}
          className={`flex items-center gap-1 rounded bg-primary px-3 py-1 text-xs font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS}`}
        >
          <Icon name="refresh" size={13} />
          <span>{t("writing.workspace.ghost.retry")}</span>
        </button>
        <button
          type="button"
          onClick={onDismiss}
          className={`rounded border border-border bg-panel px-2.5 py-1 text-xs font-medium text-muted transition-colors hover:text-foreground ${FOCUS}`}
        >
          {t("writing.workspace.ghost.discard")}
        </button>
      </div>
    </div>
  );
}

export function SceneEditor({
  body,
  onChange,
  label,
  onReady,
  continuation,
}: {
  /** The scene's plain body — initializes the document once (mount-only). */
  body: string;
  /** Every edit, the whole document as plain prose. */
  onChange: (body: string) => void;
  /** The textbox's accessible name. */
  label: string;
  /** The live instance, once mounted (null before and after) — kept in a
   *  ref here so a fresh closure per render cannot remount the editor. */
  onReady?: (editor: Editor | null) => void;
  /** The continuation's state (the page's hook) — the ghost layer renders
   *  its faces and owns the keyboard contract; absent, the prose stands
   *  alone (the read-only faces, the tests of the editor itself). */
  continuation?: Continuation;
}) {
  const emit = useRef(onChange);
  emit.current = onChange;
  const ready = useRef(onReady);
  ready.current = onReady;
  const ghost = useRef(continuation ?? null);
  ghost.current = continuation ?? null;
  const phase = continuation?.phase ?? "idle";

  const editor = useEditor({
    extensions: PROSE_EXTENSIONS,
    content: bodyToHtml(body),
    immediatelyRender: false,
    onUpdate: ({ editor: instance }) => emit.current(instance.getText()),
    editorProps: {
      attributes: {
        role: "textbox",
        "aria-multiline": "true",
        "aria-label": label,
      },
    },
  });

  useEffect(() => {
    ready.current?.(editor ?? null);
    return () => ready.current?.(null);
  }, [editor]);

  /** Tab's acceptance: the proposal joins the tail as new paragraph(s) —
   *  the plain-prose format's own join (a blank line between blocks), an
   *  empty scene takes it alone. The insertion emits through onUpdate →
   *  onChange: the autosave chain owns the write, the one path every edit
   *  rides. The ghost dismisses FIRST, so the emission finds no standing
   *  proposal to drop again. */
  const accept = useCallback(() => {
    const proposal = ghost.current;
    if (editor === null || proposal == null || proposal.phase !== "pending" || proposal.text === "") {
      return;
    }
    const html = bodyToHtml(proposal.text);
    proposal.dismiss();
    const size = editor.state.doc.content.size;
    if (editor.getText().trim() === "") {
      editor.commands.insertContentAt({ from: 0, to: size }, html);
    } else {
      editor.commands.insertContentAt(size, html);
    }
    editor.commands.focus("end");
  }, [editor]);
  const acceptRef = useRef(accept);
  acceptRef.current = accept;

  // The ghost's keyboard contract, in the CAPTURE phase: Esc dismisses
  // before the leave guard's bubble-phase handler ever sees it (the guard
  // keeps its ask — the next Esc is its own). Tab accepts only from the
  // prose, the writer's seat; everywhere else it keeps its native meaning.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const proposal = ghost.current;
      if (proposal == null || proposal.phase === "idle") return;
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        proposal.dismiss();
        return;
      }
      if (event.key === "Tab" && !event.shiftKey && proposal.phase === "pending") {
        const target = event.target;
        if (target instanceof HTMLElement && target.closest(".workspace-prose-live") !== null) {
          event.preventDefault();
          event.stopPropagation();
          acceptRef.current();
        }
      }
    }
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, []);

  // The streaming start moves the caret to the prose tail — the ghost
  // appears where the writer now sits, and Tab's seat is ready. The focus
  // lands once per streaming spell, whichever arrives last: the phase or
  // the editor instance (the mount order is not the page's to choose).
  const streamFocused = useRef(false);
  useEffect(() => {
    const phase = continuation?.phase ?? "idle";
    if (phase !== "streaming") {
      streamFocused.current = false;
      return;
    }
    if (!streamFocused.current && editor !== null) {
      streamFocused.current = true;
      editor.commands.focus("end");
    }
  }, [continuation?.phase, editor]);

  // The arrival announcement: the hidden live region stands empty from
  // mount, and its text flips AT the streaming→pending transition — a
  // live region speaks changes, never initial content, so a region mounted
  // populated (the preview span's old role) would stay silent. Leaving
  // pending clears the words: the next proposal's identical text is a
  // change again, not a silence. No other phase transition speaks.
  const t = useTranslation();
  const [arrival, setArrival] = useState("");
  const prevPhase = useRef(phase);
  useEffect(() => {
    if (prevPhase.current === "streaming" && phase === "pending") {
      setArrival(t("writing.workspace.ghost.ready"));
    } else if (phase !== "pending") {
      setArrival("");
    }
    prevPhase.current = phase;
  }, [phase, t]);

  return (
    <>
      <EditorContent
        editor={editor}
        // The editorial face the read-only port drew, inherited: the serif,
        // the draft's 1.85 leading and manuscript scale. The paragraph
        // justify, gap and drop cap ride globals.css (.workspace-prose-live).
        // The focus ring is the shell's own — visible whenever the caret is
        // inside, gone when it leaves (the MarkdownEditor's F18 pattern).
        className={`workspace-prose-live ${SERIF} rounded text-[1.18rem] leading-[1.85] text-foreground/95 focus-within:ring-2 focus-within:ring-focus md:text-[1.22rem]`}
      />
      {/* The arrival's voice — visually hidden, mounted empty, filled only
          at the streaming→pending transition (the effect above). It stands
          whenever the ghost layer does, so the words are always a CHANGE. */}
      {continuation != null && (
        <p role="status" data-testid="ghost-announcement" className="sr-only">
          {arrival}
        </p>
      )}
      {/* The ghost stands at the tail, outside the document — the scene's
          own words are the textbox's alone until Tab accepts. */}
      {phase === "streaming" && <GhostStreaming text={continuation?.text ?? ""} />}
      {phase === "pending" && <GhostPending text={continuation?.text ?? ""} onAccept={accept} />}
      {phase === "error" && (
        <GhostError onRetry={() => continuation?.retry()} onDismiss={() => continuation?.dismiss()} />
      )}
    </>
  );
}
