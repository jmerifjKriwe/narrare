"use client";

import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useState } from "react";

import { t } from "../lib/i18n";
import { SaveIndicator, useAutosave } from "../lib/save";
import { readDeltas } from "../lib/stream";

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
  const [continuing, setContinuing] = useState(false);

  const editor = useEditor({
    extensions: [StarterKit],
    content: body,
    immediatelyRender: false,
    onUpdate: ({ editor: instance }) => schedule(instance.getHTML()),
    editorProps: { attributes: { class: "prose", "aria-label": "chapter" } },
  });

  async function continueWriting() {
    if (!editor) return;
    setContinuing(true);
    try {
      const response = await fetch(
        `/api/writing/chapters/${chapterId}/continue`,
        { method: "POST" },
      );
      if (!response.ok) return;
      for await (const delta of readDeltas(response)) {
        // Append at the end: the continuation belongs after what is written.
        // Each insertion raises `onUpdate`, so the autosave persists the
        // finished text without a second endpoint writing to the chapter.
        editor.chain().focus("end").insertContent(delta).run();
      }
    } finally {
      setContinuing(false);
    }
  }

  return (
    <div>
      <div>
        <button type="button" onClick={continueWriting} disabled={continuing}>
          {t("chapters.continue")}
        </button>
        <SaveIndicator status={status} />
      </div>
      <EditorContent editor={editor} />
    </div>
  );
}
