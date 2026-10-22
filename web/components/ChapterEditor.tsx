import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useState } from "react";

import { useTranslation } from "../lib/i18n";
import { client } from "../lib/api/client";
import { SaveIndicator, useAutosave } from "../lib/save";
import { readFrames } from "../lib/stream";

export function ChapterEditor({
  chapterId,
  body,
  onSaved,
}: {
  chapterId: string;
  body: string;
  onSaved?: (chapterId: string, body: string) => void;
}) {
  const t = useTranslation();
  const { status, schedule } = useAutosave(chapterId, onSaved);
  const [continuing, setContinuing] = useState(false);
  const [failed, setFailed] = useState(false);

  const editor = useEditor({
    extensions: [StarterKit],
    content: body,
    immediatelyRender: false,
    onUpdate: ({ editor: instance }) => schedule(instance.getHTML()),
    editorProps: { attributes: { class: "prose", "aria-label": t("chapters.editorLabel") } },
  });

  async function continueWriting() {
    if (!editor) return;
    setContinuing(true);
    setFailed(false);
    try {
      // parseAs "stream": the frames are read from the body while they arrive,
      // so the client must not buffer the response first.
      const { response } = await client.POST(
        "/api/writing/chapters/{chapter_id}/continue",
        { params: { path: { chapter_id: chapterId } }, parseAs: "stream" },
      );
      if (!response.ok) {
        setFailed(true);
        return;
      }
      for await (const frame of readFrames(response)) {
        // An error frame replaces the done frame: the provider died, and a
        // silent end would look like a finished continuation.
        if (frame.error) {
          setFailed(true);
          return;
        }
        if (!frame.delta) continue;
        // Append at the end: the continuation belongs after what is written.
        // Each insertion raises `onUpdate`, so the autosave persists the
        // finished text without a second endpoint writing to the chapter.
        editor.chain().focus("end").insertContent(frame.delta).run();
      }
    } finally {
      setContinuing(false);
    }
  }

  return (
    <div className="mt-8">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={continueWriting}
          disabled={continuing}
          className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          {t("chapters.continue")}
        </button>
        <SaveIndicator status={status} />
      </div>
      {failed ? (
        <p role="alert" className="mt-2 text-sm text-danger">
          {t("chapters.continueError")}
        </p>
      ) : null}
      <EditorContent editor={editor} className="mt-6" />
    </div>
  );
}
