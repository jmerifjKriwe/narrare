"use client";

import { useMutation } from "@tanstack/react-query";
import CharacterCount from "@tiptap/extension-character-count";
import Placeholder from "@tiptap/extension-placeholder";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useTranslations } from "next-intl";
import { useEffect, useRef } from "react";
import { chaptersApi } from "@/lib/api/client";
import { useEditorStore } from "@/lib/stores/editorStore";
import { debounce } from "@/lib/utils";
import type { Chapter } from "@/types";
import { SceneBreak } from "./extensions/SceneBreak";

interface EditorSurfaceProps {
  novelId: string;
  chapter: Chapter | null;
  autosaveInterval: number; // seconds, 0 = disabled
  onWordCountUpdate: (chapterId: string, wordCount: number) => void;
}

export function EditorSurface({
  novelId,
  chapter,
  autosaveInterval,
  onWordCountUpdate,
}: EditorSurfaceProps) {
  const t = useTranslations("editor");
  const { setSaveStatus } = useEditorStore();
  const lastSavedContent = useRef<string>("");

  const saveMutation = useMutation({
    mutationFn: ({ chapterId, content }: { chapterId: string; content: string }) =>
      chaptersApi.updateContent(novelId, chapterId, content),
    onMutate: () => setSaveStatus("saving"),
    onSuccess: (updated) => {
      setSaveStatus("saved");
      lastSavedContent.current = updated.content;
      onWordCountUpdate(updated.id, updated.word_count);
    },
    onError: () => setSaveStatus("error"),
  });

  // Debounced autosave — stable ref, recreated when interval/mutation changes
  const debouncedSave = useRef(
    debounce(
      (chapterId: string, content: string) => {
        if (content !== lastSavedContent.current) {
          saveMutation.mutate({ chapterId, content });
        }
      },
      autosaveInterval > 0 ? autosaveInterval * 1000 : 30_000,
    ),
  );
  useEffect(() => {
    debouncedSave.current = debounce(
      (chapterId: string, content: string) => {
        if (content !== lastSavedContent.current) {
          saveMutation.mutate({ chapterId, content });
        }
      },
      autosaveInterval > 0 ? autosaveInterval * 1000 : 30_000,
    );
  }, [autosaveInterval, saveMutation]);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        // Disable heading to use h1/h2/h3 only
        heading: { levels: [1, 2, 3] },
      }),
      Placeholder.configure({
        placeholder: t("placeholder"),
      }),
      CharacterCount,
      SceneBreak,
    ],
    content: chapter?.content || "",
    editorProps: {
      attributes: {
        class: "narrare-editor",
        "aria-label": "Chapter editor",
        role: "textbox",
        "aria-multiline": "true",
      },
    },
    onUpdate: ({ editor }) => {
      const content = editor.getHTML();
      setSaveStatus("idle");
      if (chapter && autosaveInterval !== 0) {
        debouncedSave.current(chapter.id, content);
      }
    },
  });

  // Load chapter content when active chapter changes
  // biome-ignore lint/correctness/useExhaustiveDependencies: intentional — run only on chapter ID change, not on content/setSaveStatus changes
  useEffect(() => {
    if (!editor || !chapter) return;
    const current = editor.getHTML();
    if (current !== chapter.content) {
      editor.commands.setContent(chapter.content || "", { emitUpdate: false });
      lastSavedContent.current = chapter.content || "";
      setSaveStatus("idle");
    }
  }, [chapter?.id, editor]);

  // Manual save: Cmd/Ctrl+S
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        if (editor && chapter) {
          const content = editor.getHTML();
          saveMutation.mutate({ chapterId: chapter.id, content });
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [editor, chapter, saveMutation]);

  if (!chapter) {
    return (
      <div className="flex items-center justify-center h-full text-[var(--color-text-tertiary)] text-[0.9375rem]">
        <p>{t("addChapter")}</p>
      </div>
    );
  }

  return (
    <div className="h-full">
      <EditorContent editor={editor} className="narrare-editor" />
    </div>
  );
}
