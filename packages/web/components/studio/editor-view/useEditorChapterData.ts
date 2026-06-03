import { useQuery } from "@tanstack/react-query";
import type { Editor } from "@tiptap/react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { chaptersApi, volumesApi } from "@/lib/api/client";
import {
  recoverIfNewer,
  registerPreRedirectSave,
  saveContent,
} from "@/lib/hooks/use-content-recovery";
import { markdownToHtml } from "@/lib/utils";
import type { EditorChapterData } from "./types";

interface UseEditorChapterDataParams {
  novelId: string;
  activeChapterId: string | null;
  activeVolumeId: string | null;
  editor: Editor | null;
}

export function useEditorChapterData({
  novelId,
  activeChapterId,
  activeVolumeId,
  editor,
}: UseEditorChapterDataParams): EditorChapterData {
  const t = useTranslations("studio");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [wordCount, setWordCount] = useState(0);
  const [charCount, setCharCount] = useState(0);
  const [paragraphCount, setParagraphCount] = useState(0);
  const [sessionStartWordCount, setSessionStartWordCount] = useState(0);
  const prevChapterIdRef = useRef<string | null>(null);

  const { data: chapter, isLoading } = useQuery({
    queryKey: ["novels", novelId, "chapters", activeChapterId],
    queryFn: () => chaptersApi.get(novelId, activeChapterId!),
    enabled: !!activeChapterId,
  });

  const { data: chapters = [] } = useQuery({
    queryKey: ["novels", novelId, "chapters", activeVolumeId],
    queryFn: () => chaptersApi.list(novelId, activeVolumeId ?? undefined),
    enabled: !!novelId,
  });

  const { data: volumeStats } = useQuery({
    queryKey: ["novels", novelId, "volumes", activeVolumeId, "stats"],
    queryFn: () => volumesApi.getStats(novelId, activeVolumeId!),
    enabled: !!novelId && !!activeVolumeId,
  });

  useEffect(() => {
    if (chapter) {
      setTitle(chapter.title ?? "");
      setContent(markdownToHtml(chapter.content || ""));
    }
  }, [chapter]);

  useEffect(() => {
    if (!activeChapterId || !editor) return;
    const unregister = registerPreRedirectSave(() => {
      saveContent(activeChapterId, editor.getHTML());
    });
    return unregister;
  }, [activeChapterId, editor]);

  useEffect(() => {
    if (!chapter || !activeChapterId || !editor) return;
    const recovered = recoverIfNewer(activeChapterId, chapter.updated_at);
    if (recovered) {
      editor.commands.setContent(recovered.content);
      setContent(recovered.content);
      toast.success(t("editor.contentRecovered"));
    }
  }, [chapter, activeChapterId, editor, t]);

  useEffect(() => {
    if (chapter && chapter.id !== prevChapterIdRef.current) {
      prevChapterIdRef.current = chapter.id;
      setSessionStartWordCount(chapter.word_count);
    }
  }, [chapter]);

  useEffect(() => {
    const text = content.replace(/<[^>]*>/g, "");
    const words = text
      .trim()
      .split(/\s+/)
      .filter((word) => word.length > 0).length;
    const chars = text.length;
    const paragraphs = (content.match(/<p[\s>]/g) || []).length || 1;
    setWordCount(words);
    setCharCount(chars);
    setParagraphCount(paragraphs);
  }, [content]);

  return {
    chapter,
    chapters,
    volumeStats,
    isLoading,
    title,
    setTitle,
    content,
    setContent,
    wordCount,
    charCount,
    paragraphCount,
    sessionStartWordCount,
  };
}
