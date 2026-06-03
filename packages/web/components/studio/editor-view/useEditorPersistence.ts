import type { QueryClient } from "@tanstack/react-query";
import type { Editor } from "@tiptap/react";
import { useCallback, useState } from "react";
import { chaptersApi } from "@/lib/api/client";
import type { SaveStatus } from "@/types";
import type { EditorPersistenceActions } from "./types";

interface UseEditorPersistenceParams {
  novelId: string;
  activeChapterId: string | null;
  editor: Editor | null;
  content: string;
  title: string;
  locale: string;
  setSaveStatus: (status: SaveStatus) => void;
  queryClient: QueryClient;
}

export function useEditorPersistence({
  novelId,
  activeChapterId,
  editor,
  content,
  title,
  locale,
  setSaveStatus,
  queryClient,
}: UseEditorPersistenceParams): EditorPersistenceActions {
  const [lastSaved, setLastSaved] = useState<string | null>(null);

  const markSaved = useCallback(() => {
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
  }, [locale, novelId, queryClient, setSaveStatus]);

  const handleSave = useCallback(async () => {
    if (!activeChapterId) return;

    setSaveStatus("saving");
    try {
      const htmlContent = editor?.getHTML() ?? content;
      await Promise.all([
        chaptersApi.updateMeta(novelId, activeChapterId, { title }),
        chaptersApi.updateContent(novelId, activeChapterId, htmlContent),
      ]);
      markSaved();
    } catch {
      setSaveStatus("error");
    }
  }, [activeChapterId, editor, novelId, content, title, setSaveStatus, markSaved]);

  const handleAutosave = useCallback(
    async (htmlContent: string) => {
      if (!activeChapterId) return;
      setSaveStatus("saving");
      try {
        await Promise.all([
          chaptersApi.updateContent(novelId, activeChapterId, htmlContent),
          chaptersApi.updateMeta(novelId, activeChapterId, { title }),
        ]);
        markSaved();
      } catch {
        setSaveStatus("error");
      }
    },
    [activeChapterId, novelId, title, setSaveStatus, markSaved],
  );

  return { handleSave, handleAutosave, lastSaved };
}
