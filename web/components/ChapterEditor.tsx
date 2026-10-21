"use client";

import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";

import { SaveIndicator, useAutosave } from "../lib/save";

export function ChapterEditor({
  chapterId,
  body,
  onSaved,
}: {
  chapterId: string;
  body: string;
  onSaved?: (chapterId: string, body: string) => void;
}) {
  const { status, schedule } = useAutosave(chapterId, onSaved);

  const editor = useEditor({
    extensions: [StarterKit],
    content: body,
    immediatelyRender: false,
    onUpdate: ({ editor: instance }) => schedule(instance.getHTML()),
    editorProps: { attributes: { class: "prose", "aria-label": "chapter" } },
  });

  return (
    <div>
      <SaveIndicator status={status} />
      <EditorContent editor={editor} />
    </div>
  );
}
