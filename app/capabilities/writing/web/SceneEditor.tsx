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
 * its invalidation family), exactly as a typed edit does. The pending
 * preview draws the SAME structure the insertion carries — the shared
 * proseBlocks split (bodyToHtml's own), paragraphs and hard breaks alike.
 *
 * The draft's area-writing/70 ink fails the axe AA floor on both themes
 * (~3.2:1 light, ~3.9:1 dark on the paper); the ink rides full strength
 * (6.1:1 / 6.6:1) and the /5 wash carries the softness — the amber pill's
 * own discipline (Task 12): the identity stays, the floor is kept.
 *
 * The zen focus dimming (W4 Task 18, D6): a decoration plugin dims the
 * prose outside the caret's paragraph (Absatz-Fokus) or sentence
 * (Satz-Fokus); Normal dims nothing. The mode arrives by meta transaction
 * from the zen surface's segment control — one extension set for the
 * editor's life, the caret never dropped by a rebuild. The dimming follows
 * every doc change and selection move; the sentence geometry is the zen
 * seam's pure splitter, the position mapping the document's own (a hard
 * break is whitespace to the splitter, never a decoratable span).
 *
 * The editable seam (the Codacy swap-window fix): the page's zen transition
 * (flush → invalidate → refetch → swap) locks the live prose through the
 * `editable` prop — TipTap's setEditable, no update emission, no remount —
 * so keystrokes in the window cannot die with the unmount; the ghost's Tab
 * acceptance waits with the lock.
 */
import { EditorContent, useEditor } from "@tiptap/react";
import { Extension, type Editor } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import type { Node } from "@tiptap/pm/model";
import type { Selection } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";
import StarterKit from "@tiptap/starter-kit";
import { Fragment, useCallback, useEffect, useRef, useState } from "react";

import { useTranslation } from "@shell/lib/i18n";
import { Icon } from "@shell/ui/icons";

import { activeSentence, type Continuation, type ZenFocusMode } from "./workspace";

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The shell's focus ring on the ghost's one control. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The proposal's editorial face — the prose's own scale and leading, the
 *  italic voice the draft draws, the writing area's ink at full strength
 *  (the AA floor; the docblock above carries the measured reason). */
const GHOST_PROSE = `${SERIF} text-[1.18rem] italic leading-[1.85] text-area-writing md:text-[1.22rem]`;

// --- The zen focus dimming (W4 Task 18) -------------------------------------
//
// The draft's Absatz-/Satz-/Normal presets, frontend-real (D6): a decoration
// plugin that dims everything outside the caret's paragraph (Absatz) or
// sentence (Satz) and dims nothing at all (Normal). The mode arrives as a
// meta transaction (the zen surface's segment control), the decorations
// recompute on every doc change and selection move — the dimming follows
// the caret honestly. The classes ride globals.css (.zen-dim-block,
// .zen-dim-inline, .zen-active-block); the sentence geometry is the zen
// seam's pure splitter (workspace.ts), the position mapping here is the
// document's own — a hard break is whitespace to the splitter but carries
// no text position, so the inline spans never swallow it.

/** The plugin's meta key — the mode transaction's own door. */
const ZEN_FOCUS = new PluginKey("zenFocus");

interface ZenFocusPluginState {
  mode: ZenFocusMode;
  decorations: DecorationSet;
}

/** One textblock's characters with their DOCUMENT positions: text nodes
 *  map one-to-one, a hard break reads as whitespace to the sentence
 *  splitter but is not decoratable text (it has no text position). */
function textblockCharMap(node: Node, blockFrom: number) {
  const chars: string[] = [];
  const positions: number[] = [];
  const decoratable: boolean[] = [];
  node.forEach((child, offset) => {
    const text = child.text;
    if (child.isText && text != null) {
      for (let at = 0; at < text.length; at += 1) {
        chars.push(text[at]);
        positions.push(blockFrom + offset + at);
        decoratable.push(true);
      }
    } else if (child.type.name === "hardBreak") {
      chars.push("\n");
      positions.push(blockFrom + offset);
      decoratable.push(false);
    }
  });
  return { text: chars.join(""), positions, decoratable };
}

/** The inline spans one dim range asks for — consecutive decoratable
 *  characters grouped, a hard break (or any gap) splitting the span. */
function dimRange(
  from: number,
  to: number,
  map: ReturnType<typeof textblockCharMap>,
  decos: Decoration[],
): void {
  let start = -1;
  for (let at = from; at <= to; at += 1) {
    const solid = at < to && map.decoratable[at];
    if (solid && start === -1) start = at;
    if (!solid && start !== -1) {
      decos.push(
        Decoration.inline(map.positions[start], map.positions[at - 1] + 1, { class: "zen-dim-inline" }),
      );
      start = -1;
    }
  }
}

/** The decorations one mode asks for on the current document and caret. */
function focusDecorations(mode: ZenFocusMode, doc: Node, selection: Selection): DecorationSet {
  if (mode === "normal") return DecorationSet.empty;
  const head = selection.head;
  const decos: Decoration[] = [];
  if (mode === "paragraph") {
    // The top-level block the caret sits in stands; every other dims. The
    // prose is flat paragraphs (the StarterKit's prose-only set), so the
    // document's own children are the blocks.
    let activeIndex = -1;
    let at = 0;
    let index = 0;
    doc.forEach((node) => {
      if (head >= at && head <= at + node.nodeSize) activeIndex = index;
      at += node.nodeSize;
      index += 1;
    });
    at = 0;
    index = 0;
    doc.forEach((node) => {
      const cls = index === activeIndex ? "zen-active-block" : "zen-dim-block";
      decos.push(Decoration.node(at, at + node.nodeSize, { class: cls }));
      at += node.nodeSize;
      index += 1;
    });
    return DecorationSet.create(doc, decos);
  }
  // Sentence mode: every textblock's text outside the caret's sentence
  // dims inline — the caret's block keeps its active span, every other
  // block dims wholly.
  doc.descendants((node, pos) => {
    if (!node.isTextblock) return;
    const map = textblockCharMap(node, pos + 1);
    if (map.text === "") return;
    const caretInside = head >= pos && head <= pos + node.nodeSize;
    let caretOffset = 0;
    if (caretInside) {
      for (const position of map.positions) {
        if (position < head) caretOffset += 1;
      }
    }
    const active = caretInside ? activeSentence(map.text, caretOffset) : null;
    if (active === null) {
      dimRange(0, map.text.length, map, decos);
      return;
    }
    if (active[0] > 0) dimRange(0, active[0], map, decos);
    if (active[1] < map.text.length) dimRange(active[1], map.text.length, map, decos);
  });
  return DecorationSet.create(doc, decos);
}

/** The focus plugin — one instance shared by every editor (the plugin
 *  STATE is per-editor, ProseMirror's own); the mode rides meta, the
 *  decorations follow the document and the caret. */
const zenFocusExtension = Extension.create({
  name: "zenFocus",
  addProseMirrorPlugins() {
    return [
      new Plugin<ZenFocusPluginState>({
        key: ZEN_FOCUS,
        state: {
          init: () => ({ mode: "normal", decorations: DecorationSet.empty }),
          apply(tr, old) {
            const meta = tr.getMeta(ZEN_FOCUS) as ZenFocusMode | undefined;
            if (meta === undefined && !tr.docChanged && !tr.selectionSet) return old;
            const mode = meta ?? old.mode;
            return { mode, decorations: focusDecorations(mode, tr.doc, tr.selection) };
          },
        },
        props: {
          decorations(state) {
            return ZEN_FOCUS.getState(state)?.decorations ?? DecorationSet.empty;
          },
        },
      }),
    ];
  },
});

/** Prose only: the StarterKit with every non-prose node and mark disabled.
 *  One identity for the component's life — a fresh array per render would
 *  rebuild the editor. Document, paragraph, text, hardBreak and undoRedo
 *  stay; the draft draws no heading, list, quote, rule or formatting. The
 *  zen focus plugin rides along at rest (mode „normal", no decorations) —
 *  one extension set for the component's life, the mode arrives by meta
 *  transaction, never by a rebuild that would drop the caret. */
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
  zenFocusExtension,
];

function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/**
 * The plain body's paragraph blocks — the ONE split the editor's
 * initialization HTML, the acceptance insertion and the ghost's preview
 * all draw from: blank lines separate paragraphs (the read-only port's own
 * rule), each block trimmed, empty blocks dropped. One home, so the
 * preview can never drift from the structure Tab inserts.
 */
export function proseBlocks(body: string): string[] {
  return body
    .split(/\n[ \t]*\n/)
    .map((block) => block.trim())
    .filter((block) => block !== "");
}

/**
 * The plain body as the HTML the editor initializes from (and the
 * acceptance inserts): the shared blocks, single newlines as hard breaks,
 * the markup characters prose may carry escaped. An empty or
 * whitespace-only body is one empty paragraph — the paper stays honest,
 * never an invented sentence. Trimming each block mirrors the read-only
 * rendering, so the first non-empty paragraph wears the drop cap.
 */
export function bodyToHtml(body: string): string {
  const blocks = proseBlocks(body);
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
 *  the [Tab] keycap pill inline after the LAST paragraph. The preview draws
 *  the very structure acceptance inserts: the acceptance path's own blocks
 *  (proseBlocks — bodyToHtml's split), paragraphs and hard breaks alike,
 *  the blank-line gap the live prose wears between paragraphs (p + p). The
 *  draft's single-block geometry stays: one preview block, the pill inline
 *  at its tail. The pill is a real button (the dark face draws it as one):
 *  pointer users accept by click, the keyboard by Tab from the prose or
 *  Enter on the pill itself. The preview is NOT a live region — a span
 *  mounted populated never speaks; the arrival is announced by the
 *  editor's hidden region at the transition instead. */
function GhostPending({ text, onAccept }: { text: string; onAccept: () => void }) {
  const t = useTranslation();
  const blocks = proseBlocks(text);
  const paragraphs = blocks.length === 0 ? [""] : blocks;
  return (
    <div data-testid="ghost-preview" className="mt-6">
      <div className={`${GHOST_PROSE} text-justify [&_p+p]:mt-6`}>
        {paragraphs.map((block, at) => (
          <p key={at}>
            <span className="rounded bg-area-writing/5 px-1 py-0.5">
              {block.split("\n").map((line, index) => (
                <Fragment key={index}>
                  {index > 0 && <br />}
                  {line}
                </Fragment>
              ))}
            </span>
            {at === paragraphs.length - 1 && (
              <button
                type="button"
                onClick={onAccept}
                aria-keyshortcuts="Tab"
                className={`ml-2 inline-flex items-center gap-1.5 rounded-full bg-primary px-2 py-0.5 align-middle font-sans text-[11px] font-medium not-italic text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS}`}
              >
                <kbd className="rounded border border-primary-foreground/40 px-1 font-mono text-[10px]">Tab</kbd>
                <span>{t("writing.workspace.ghost.accept")}</span>
              </button>
            )}
          </p>
        ))}
      </div>
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
  focus,
  autoFocus,
  editable = true,
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
  /** The zen focus preset (W4 Task 18) — the dimming the plugin draws.
   *  Absent or „normal": the prose stands at full strength, the workspace's
   *  own face. The mode rides a meta transaction, never an editor rebuild. */
  focus?: ZenFocusMode;
  /** Focus the prose tail once the editor mounts — the zen entry's seat
   *  (the writer lands where the writing continues). */
  autoFocus?: boolean;
  /** The zen swap window's lock (the Codacy fix): false makes the LIVE
   *  prose non-editable — TipTap's own editability, contenteditable flipped,
   *  ProseMirror gating the edit events — so keystrokes in the transition
   *  window (flush → invalidate → refetch → swap) cannot die with the
   *  unmount. The lock lifts on the same instance, never a remount; the
   *  ghost's Tab acceptance waits with it. Default true: the writing face. */
  editable?: boolean;
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

  // The zen focus mode (Task 18): a meta transaction carries the preset to
  // the plugin — the decorations recompute, the caret never moves. The
  // dispatch only fires on a real change (the plugin's own state is the
  // authority), so a re-render cannot spam the document with transactions.
  const focusMode = focus ?? "normal";
  useEffect(() => {
    if (editor === null) return;
    const current = ZEN_FOCUS.getState(editor.state)?.mode ?? "normal";
    if (current !== focusMode) {
      editor.view.dispatch(editor.state.tr.setMeta(ZEN_FOCUS, focusMode));
    }
  }, [editor, focusMode]);

  // The swap window's lock (the Codacy fix): editability rides TipTap's own
  // setEditable — the view's contenteditable flips and ProseMirror gates the
  // edit events, the caret and the document untouched. No update emission:
  // a lock is not an edit, and a phantom onChange would schedule an autosave
  // of unchanged words. The effect runs on the live instance, so the lock
  // falls and lifts without a remount (a remount would re-initialize the
  // body — the very loss the window exists to prevent).
  useEffect(() => {
    if (editor === null) return;
    if (editor.isEditable !== editable) editor.setEditable(editable, false);
  }, [editor, editable]);

  // The zen entry's seat: the caret lands at the prose tail once the
  // instance exists — the writer continues where the scene stands.
  useEffect(() => {
    if (editor !== null && autoFocus) editor.commands.focus("end");
  }, [editor, autoFocus]);

  /** Tab's acceptance: the proposal joins the tail as new paragraph(s) —
   *  the plain-prose format's own join (a blank line between blocks), an
   *  empty scene takes it alone. The insertion emits through onUpdate →
   *  onChange: the autosave chain owns the write, the one path every edit
   *  rides. The ghost dismisses FIRST, so the emission finds no standing
   *  proposal to drop again. */
  const accept = useCallback(() => {
    const proposal = ghost.current;
    // A locked prose (the swap window) refuses the acceptance too: the
    // inserted words would die with the unmount. The proposal stands for
    // the next face — the page's one continuation rides the swap.
    if (
      editor === null ||
      !editor.isEditable ||
      proposal == null ||
      proposal.phase !== "pending" ||
      proposal.text === ""
    ) {
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
