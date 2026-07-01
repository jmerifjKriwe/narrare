import Placeholder from "@tiptap/extension-placeholder";
import { useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import type { useTranslations } from "next-intl";
import { useEffect } from "react";
import { useEditorStore } from "@/lib/stores/editorStore";
import { markdownToHtml } from "@/lib/utils";
import { AIAnnotationExtension, AIAnnotationMark } from "./extensions/AIAnnotation";
import { Autosave, type AutosaveOptions } from "./extensions/Autosave";
import { DialogueMark } from "./extensions/DialogueMark";
import { GhostText, type GhostTextOptions } from "./extensions/GhostText";
import { NarrareDocument } from "./extensions/NarrareDocument";
import { SceneBreak } from "./extensions/SceneBreak";

type Translator = ReturnType<typeof useTranslations>;

interface UseEditorInstanceParams {
  content: string;
  onChange: (content: string) => void;
  autosaveConfig: Partial<AutosaveOptions>;
  ghostTextConfig: Partial<GhostTextOptions>;
  t: Translator;
}

/**
 * Creates and synchronizes the TipTap editor instance.
 *
 * Owns a single responsibility: instantiate the editor with the Narrare
 * extension stack (StarterKit + document/scene/dialogue/AI marks + autosave &
 * ghost-text extensions configured externally), keep its content in sync with
 * the host, and register it on the global editor store + window so non-React
 * tooling (bubble menu, slash commands, debug hooks) can reach it.
 */
export function useEditorInstance({
  content,
  onChange,
  autosaveConfig,
  ghostTextConfig,
  t,
}: UseEditorInstanceParams) {
  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit.configure({ document: false, heading: { levels: [1, 2, 3] } }),
      NarrareDocument,
      SceneBreak,
      DialogueMark,
      AIAnnotationMark,
      AIAnnotationExtension,
      Autosave.configure(autosaveConfig),
      GhostText.configure(ghostTextConfig),
      Placeholder.configure({ placeholder: t("editor.placeholder") }),
    ],
    content,
    onUpdate: ({ editor: ed }) => onChange(ed.getHTML()),
    editorProps: { attributes: { class: "max-w-none focus:outline-none min-h-[70vh] py-6 pr-8" } },
  });

  // Keep the editor content in sync when the host `content` prop changes
  // externally (e.g. chapter switch).
  useEffect(() => {
    if (editor && content !== editor.getHTML())
      editor.commands.setContent(
        content.trim().startsWith("<") ? content : markdownToHtml(content),
      );
  }, [content, editor]);

  useEffect(() => {
    if (!editor) return;
    useEditorStore.getState().setEditor(editor);
    if (typeof window !== "undefined")
      (window as unknown as Window & { __narrareEditor: unknown }).__narrareEditor = editor;
  }, [editor]);

  return editor;
}
