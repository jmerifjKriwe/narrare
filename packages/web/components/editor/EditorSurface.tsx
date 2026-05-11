"use client"

import { useEffect, useCallback, useRef } from "react"
import { useEditor, EditorContent } from "@tiptap/react"
import StarterKit from "@tiptap/starter-kit"
import Placeholder from "@tiptap/extension-placeholder"
import CharacterCount from "@tiptap/extension-character-count"
import { useTranslations } from "next-intl"
import { useMutation } from "@tanstack/react-query"
import { chaptersApi } from "@/lib/api/client"
import { useEditorStore } from "@/lib/stores/editorStore"
import { SceneBreak } from "./extensions/SceneBreak"
import { debounce } from "@/lib/utils"

interface EditorSurfaceProps {
  novelId: string
  autosaveInterval: number // seconds, 0 = disabled
}

export function EditorSurface({ novelId, autosaveInterval }: EditorSurfaceProps) {
  const t = useTranslations("editor")
  const { activeChapter, setSaveStatus, updateChapterWordCount } = useEditorStore()
  const lastSavedContent = useRef<string>("")
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const saveMutation = useMutation({
    mutationFn: ({ chapterId, content }: { chapterId: string; content: string }) =>
      chaptersApi.updateContent(novelId, chapterId, content),
    onMutate: () => setSaveStatus("saving"),
    onSuccess: (chapter) => {
      setSaveStatus("saved")
      lastSavedContent.current = chapter.content
      updateChapterWordCount(chapter.id, chapter.word_count)
    },
    onError: () => setSaveStatus("error"),
  })

  // Debounced save function
  const scheduleSave = useCallback(
    (chapterId: string, content: string) => {
      const doSave = debounce((cid: string, html: string) => {
        if (html !== lastSavedContent.current) {
          saveMutation.mutate({ chapterId: cid, content: html })
        }
      }, autosaveInterval > 0 ? autosaveInterval * 1000 : 30_000)
      doSave(chapterId, content)
    },
    [autosaveInterval, saveMutation]
  )

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
    content: activeChapter?.content || "",
    editorProps: {
      attributes: {
        class: "narrare-editor",
        "aria-label": "Chapter editor",
        role: "textbox",
        "aria-multiline": "true",
      },
    },
    onUpdate: ({ editor }) => {
      const content = editor.getHTML()
      setSaveStatus("idle")
      if (activeChapter && autosaveInterval !== 0) {
        scheduleSave(activeChapter.id, content)
      }
    },
  })

  // Load chapter content when active chapter changes
  useEffect(() => {
    if (!editor || !activeChapter) return
    const current = editor.getHTML()
    if (current !== activeChapter.content) {
      // Clear any pending save for previous chapter
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
      editor.commands.setContent(activeChapter.content || "", { emitUpdate: false })
      lastSavedContent.current = activeChapter.content || ""
      setSaveStatus("idle")
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional: run only on chapter ID change
  }, [activeChapter?.id, editor])

  // Manual save: Cmd/Ctrl+S
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault()
        if (editor && activeChapter) {
          const content = editor.getHTML()
          saveMutation.mutate({ chapterId: activeChapter.id, content })
        }
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [editor, activeChapter, saveMutation])

  if (!activeChapter) {
    return (
      <div className="editor-surface-empty">
        <p>{t("addChapter")}</p>
        <style jsx>{`
          .editor-surface-empty {
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100%;
            color: var(--color-text-tertiary);
            font-size: 0.9375rem;
          }
        `}</style>
      </div>
    )
  }

  return (
    <div className="editor-surface">
      <EditorContent editor={editor} className="narrare-editor" />

      <style jsx>{`
        .editor-surface {
          height: 100%;
        }
        /* Global TipTap styles — need global scope */
        :global(.narrare-editor .ProseMirror) {
          font-family: var(--font-serif);
          font-size: var(--editor-font-size);
          line-height: var(--editor-line-height);
          color: var(--color-text-primary);
          max-width: var(--editor-max-width);
          margin: 0 auto;
          padding: var(--space-12) var(--space-4);
          outline: none;
          min-height: calc(100vh - 100px);
        }
        :global(.narrare-editor .ProseMirror p) {
          margin-bottom: 1em;
        }
        :global(.narrare-editor .ProseMirror p.is-editor-empty:first-child::before) {
          content: attr(data-placeholder);
          color: var(--color-text-placeholder);
          pointer-events: none;
          float: left;
          height: 0;
        }
        :global(.narrare-editor .ProseMirror h1) { font-size: 1.75rem; font-weight: 700; margin: 2em 0 0.5em; font-family: var(--font-sans); }
        :global(.narrare-editor .ProseMirror h2) { font-size: 1.375rem; font-weight: 600; margin: 1.5em 0 0.5em; font-family: var(--font-sans); }
        :global(.narrare-editor .ProseMirror h3) { font-size: 1.125rem; font-weight: 600; margin: 1.25em 0 0.4em; font-family: var(--font-sans); }
      `}</style>
    </div>
  )
}
