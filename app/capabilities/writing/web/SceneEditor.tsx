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
 */
import { EditorContent, useEditor } from "@tiptap/react";
import type { Editor } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import { useEffect, useRef } from "react";

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

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

export function SceneEditor({
  body,
  onChange,
  label,
  onReady,
}: {
  /** The scene's plain body — initializes the document once (mount-only). */
  body: string;
  /** Every edit, the whole document as plain prose. */
  onChange: (body: string) => void;
  /** The textbox's accessible name. */
  label: string;
  /** The live instance, once mounted (null before and after) — the ghost
   *  layer (PR 4) drives the view; kept in a ref here so a fresh closure per
   *  render cannot remount the editor. */
  onReady?: (editor: Editor | null) => void;
}) {
  const emit = useRef(onChange);
  emit.current = onChange;
  const ready = useRef(onReady);
  ready.current = onReady;

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

  return (
    <EditorContent
      editor={editor}
      // The editorial face the read-only port drew, inherited: the serif,
      // the draft's 1.85 leading and manuscript scale. The paragraph
      // justify, gap and drop cap ride globals.css (.workspace-prose-live).
      // The focus ring is the shell's own — visible whenever the caret is
      // inside, gone when it leaves (the MarkdownEditor's F18 pattern).
      className={`workspace-prose-live ${SERIF} rounded text-[1.18rem] leading-[1.85] text-foreground/95 focus-within:ring-2 focus-within:ring-focus md:text-[1.22rem]`}
    />
  );
}
