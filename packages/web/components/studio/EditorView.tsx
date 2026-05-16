"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Clock, Save, Sparkles } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { chaptersApi } from "@/lib/api/client";
import { useEditorStore } from "@/lib/stores/editorStore";
import { markdownToHtml } from "@/lib/utils";
import { TipTapEditor } from "./TipTapEditor";

interface EditorViewProps {
  novelId: string;
}

export function EditorView({ novelId }: EditorViewProps) {
  const t = useTranslations("studio");
  const locale = useLocale();
  const queryClient = useQueryClient();

  const activeChapterId = useEditorStore((s) => s.activeChapterId);
  const editor = useEditorStore((s) => s.editor);
  const setSaveStatus = useEditorStore((s) => s.setSaveStatus);

  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [wordCount, setWordCount] = useState(0);
  const [charCount, setCharCount] = useState(0);
  const [lastSaved, setLastSaved] = useState<string | null>(null);

  // Fetch active chapter content
  const { data: chapter, isLoading } = useQuery({
    queryKey: ["novels", novelId, "chapters", activeChapterId],
    queryFn: () => chaptersApi.get(novelId, activeChapterId!),
    enabled: !!activeChapterId,
  });

  // Sync title and content from API data
  useEffect(() => {
    if (chapter) {
      setTitle(chapter.title);
      setContent(markdownToHtml(chapter.content || ""));
    }
  }, [chapter]);

  // Compute word and character counts
  useEffect(() => {
    const text = content.replace(/<[^>]*>/g, "");
    const words = text
      .trim()
      .split(/\s+/)
      .filter((w) => w.length > 0).length;
    const chars = text.length;
    setWordCount(words);
    setCharCount(chars);
  }, [content]);

  async function handleSave() {
    if (!activeChapterId) return;

    setSaveStatus("saving");
    try {
      await Promise.all([
        chaptersApi.updateContent(novelId, activeChapterId, content),
        chaptersApi.updateMeta(novelId, activeChapterId, { title }),
      ]);
      setSaveStatus("saved");
      setLastSaved(
        new Date().toLocaleTimeString(locale, {
          hour: "2-digit",
          minute: "2-digit",
        }),
      );
      queryClient.invalidateQueries({
        queryKey: ["novels", novelId, "chapters"],
      });
    } catch {
      setSaveStatus("error");
    }
  }

  const readingTime = Math.ceil(wordCount / 200);

  // No chapter selected
  if (!activeChapterId) {
    return (
      <div className="flex-1 flex items-center justify-center h-full text-muted-foreground">
        <p>{t("editor.selectChapter")}</p>
      </div>
    );
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center h-full">
        <div className="w-8 h-8 rounded-md bg-primary animate-pulse" />
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-background">
      {/* Header bar */}
      <div className="border-b border-border px-8 py-4 flex items-center justify-between bg-card">
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="bg-transparent border-none outline-none flex-1 mr-4 text-lg font-medium"
          placeholder={t("editor.chapterTitlePlaceholder")}
        />
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Clock className="w-4 h-4" />
            <span>{lastSaved ?? "--:--"}</span>
          </div>
          <button
            type="button"
            onClick={handleSave}
            className="flex items-center gap-2 px-5 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity shadow-sm"
          >
            <Save className="w-4 h-4" />
            <span className="text-sm">{t("editor.save")}</span>
          </button>
        </div>
      </div>

      {/* Formatting toolbar */}
      {editor && (
        <div className="border-b border-border px-8 py-2 bg-card flex items-center gap-1">
          <button
            type="button"
            onClick={() => editor.chain().focus().toggleBold().run()}
            className={`p-1.5 rounded hover:bg-accent transition-colors text-sm ${
              editor.isActive("bold") ? "bg-accent" : ""
            }`}
            title={t("editor.bold")}
          >
            <strong>{"B"}</strong>
          </button>
          <button
            type="button"
            onClick={() => editor.chain().focus().toggleItalic().run()}
            className={`p-1.5 rounded hover:bg-accent transition-colors text-sm ${
              editor.isActive("italic") ? "bg-accent" : ""
            }`}
            title={t("editor.italic")}
          >
            <em>{"I"}</em>
          </button>
          <div className="w-px h-5 bg-border mx-1" />
          <button
            type="button"
            onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
            className={`p-1.5 rounded hover:bg-accent transition-colors text-sm ${
              editor.isActive("heading", { level: 2 }) ? "bg-accent" : ""
            }`}
            title={t("editor.heading2")}
          >
            {"H2"}
          </button>
          <button
            type="button"
            onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
            className={`p-1.5 rounded hover:bg-accent transition-colors text-sm ${
              editor.isActive("heading", { level: 3 }) ? "bg-accent" : ""
            }`}
            title={t("editor.heading3")}
          >
            {"H3"}
          </button>
          <div className="w-px h-5 bg-border mx-1" />
          <button
            type="button"
            onClick={() => editor.chain().focus().toggleBlockquote().run()}
            className={`p-1.5 rounded hover:bg-accent transition-colors text-sm ${
              editor.isActive("blockquote") ? "bg-accent" : ""
            }`}
            title={t("editor.blockquote")}
          >
            {"\u201C"}
          </button>
        </div>
      )}

      {/* Editor area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto">
          <TipTapEditor content={content} onChange={setContent} />
        </div>
      </div>

      {/* Status bar */}
      <div className="border-t border-border px-8 py-3 bg-card">
        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center gap-6 text-muted-foreground">
            <span>{t("editor.words", { count: wordCount })}</span>
            <span>{t("editor.characters", { count: charCount })}</span>
            <span>{t("editor.readingTime", { minutes: readingTime })}</span>
          </div>
          <div className="flex items-center gap-2 text-muted-foreground">
            <Sparkles className="w-3.5 h-3.5" />
            <span className="text-xs">{t("editor.aiActive")}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
