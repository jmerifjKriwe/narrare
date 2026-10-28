import { EditorContent, useEditor } from "@tiptap/react";
import type { Editor, Extensions } from "@tiptap/core";
import { Markdown } from "@tiptap/markdown";
import StarterKit from "@tiptap/starter-kit";
import { useEffect, useMemo, useRef } from "react";

/** The omitted-extensions default, one identity for the component's life:
 *  the memo that appends it would recompute on every render if each render
 *  handed it a fresh `[]`. */
const NO_EXTENSIONS: Extensions = [];

/**
 * The shell's Markdown editor: one TipTap instance whose content is Markdown
 * in and Markdown out. `value` initializes the document as Markdown source
 * (remount with a new key to switch documents); every update emits the whole
 * document as Markdown through `onChange` — Markdown is the storage format,
 * not a view of some HTML underneath. Rich text on screen, Markdown in the
 * store.
 *
 * The editable element is a real labelled textbox — the same `prose` paint,
 * explicit `role`, multiline and `aria-label` the chapter editor carries
 * (@tiptap/core injects role="textbox" in createView, but the React binding
 * strips it again: EditorContent.init() re-parents the view and
 * setOptions({element}) re-props it from the raw editorProps — the explicit
 * role keeps aria-label valid; axe computes "generic" for the roleless div
 * and flags aria-prohibited-attr deterministically while the editor is
 * empty).
 *
 * `extensions` composes extras into the same editor (the chapter editor's
 * ghost text); `onReady` hands out the live instance for callers that must
 * drive the view (caret, decorations). Both stay optional: the entity
 * dialog's body field passes none of them.
 */
export function MarkdownEditor({
  value,
  onChange,
  label,
  extensions = NO_EXTENSIONS,
  onReady,
  className,
}: {
  value: string;
  onChange: (markdown: string) => void;
  label: string;
  /** Extra extensions composed into the editor, created once with it. */
  extensions?: Extensions;
  /** The live instance, once mounted (null before and after). Kept in a ref
   *  on this side, so a fresh closure per render cannot remount the editor. */
  onReady?: (editor: Editor | null) => void;
  className?: string;
}) {
  const emit = useRef(onChange);
  emit.current = onChange;
  const ready = useRef(onReady);
  ready.current = onReady;

  const all = useMemo(() => [StarterKit, Markdown, ...extensions], [extensions]);
  const editor = useEditor({
    extensions: all,
    content: value,
    contentType: "markdown",
    immediatelyRender: false,
    onUpdate: ({ editor: instance }) => emit.current(instance.getMarkdown()),
    editorProps: {
      attributes: {
        class: "prose",
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

  return <EditorContent editor={editor} className={className} />;
}
