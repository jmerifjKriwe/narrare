"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Clock, Save } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { NameGeneratorModal } from "@/components/generation/NameGeneratorModal";
import { chaptersApi, settingsApi } from "@/lib/api/client";
import { useEditorStore } from "@/lib/stores/editorStore";
import type { ChapterSummary } from "@/types";
import { CommandPalette } from "./CommandPalette";
import { ContextPanel } from "./ContextPanel";
import { EditorSurface } from "./EditorSurface";
import { StatusBar } from "./StatusBar";

interface EditorLayoutProps {
  novelId: string;
}

export function EditorLayout({ novelId }: EditorLayoutProps) {
  const t = useTranslations("editor");

  const {
    activeChapterId,
    setActiveChapterId,
    contextPanelOpen,
    focusMode,
    editor,
    lastSavedAt,
    toggleSidebar,
    toggleContextPanel,
    toggleFocusMode,
  } = useEditorStore();

  const queryClient = useQueryClient();
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [nameGeneratorOpen, setNameGeneratorOpen] = useState(false);

  // Server data — direct from TanStack Query, no store sync
  const { data: chapters = [] } = useQuery({
    queryKey: ["chapters", novelId],
    queryFn: () => chaptersApi.list(novelId),
  });

  const { data: activeChapter } = useQuery({
    queryKey: ["chapter", novelId, activeChapterId],
    queryFn: () =>
      activeChapterId ? chaptersApi.get(novelId, activeChapterId) : Promise.resolve(null),
    enabled: !!activeChapterId,
  });

  const { data: settings } = useQuery({
    queryKey: ["settings", "project", novelId],
    queryFn: () => settingsApi.getProject(novelId),
  });

  // Title update mutation
  const titleMutation = useMutation({
    mutationFn: ({ chapterId, title }: { chapterId: string; title: string }) =>
      chaptersApi.updateMeta(novelId, chapterId, { title }),
    onSuccess: (updated) => {
      queryClient.setQueryData(["chapter", novelId, activeChapterId], updated);
      // Also update the chapter in the list cache
      const currentChapters =
        queryClient.getQueryData<ChapterSummary[]>(["chapters", novelId]) ?? [];
      queryClient.setQueryData(
        ["chapters", novelId],
        currentChapters.map((c) => (c.id === updated.id ? { ...c, title: updated.title } : c)),
      );
    },
  });

  // Auto-select first chapter when chapters load and none is active
  useEffect(() => {
    if (chapters.length > 0 && !activeChapterId) {
      setActiveChapterId(chapters[0].id);
    }
  }, [chapters, activeChapterId, setActiveChapterId]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Toggle command palette
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCommandPaletteOpen((prev) => !prev);
      }
      if ((e.metaKey || e.ctrlKey) && e.key === "\\") {
        e.preventDefault();
        toggleSidebar();
      }
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === "F") {
        e.preventDefault();
        toggleFocusMode();
      }
      if (e.key === "Escape" && useEditorStore.getState().focusMode) {
        e.preventDefault();
        toggleFocusMode();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [toggleSidebar, toggleFocusMode]);

  const autosaveInterval = settings?.autosave_interval ?? 30;

  // Callback for word count optimistic updates — syncs TanStack Query cache
  const handleWordCountUpdate = (chapterId: string, wordCount: number) => {
    const currentChapters = queryClient.getQueryData<ChapterSummary[]>(["chapters", novelId]) ?? [];
    const updated = useEditorStore
      .getState()
      .updateChapterWordCount(chapterId, wordCount, currentChapters);
    queryClient.setQueryData(["chapters", novelId], updated);
  };

  // Title change handler
  const handleTitleChange = (newTitle: string) => {
    if (activeChapterId && newTitle.trim()) {
      titleMutation.mutate({ chapterId: activeChapterId, title: newTitle });
    }
  };

  // Manual save handler for the inline save button
  const handleManualSave = () => {
    if (editor && activeChapter) {
      const autosave = editor.extensionManager.extensions.find(
        (ext: { name: string }) => ext.name === "autosave",
      );
      if (autosave && "storage" in autosave) {
        const storage = autosave.storage as { forceSave: () => Promise<void> };
        storage.forceSave();
      }
    }
  };

  // Format last saved time as HH:MM
  const formatLastSaved = (date: Date | null): string => {
    if (!date) return "--:--";
    return date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-background">
      {/* Inline Header — hidden in focus mode */}
      {!focusMode && (
        <div className="border-b border-border/40 px-10 py-5 flex items-center justify-between bg-background shrink-0">
          <div className="flex-1 max-w-2xl">
            <input
              type="text"
              value={activeChapter?.title ?? ""}
              onChange={(e) => handleTitleChange(e.target.value)}
              className="bg-transparent border-none outline-none w-full text-xl font-bold text-foreground placeholder:text-muted-foreground/30 transition-all focus:placeholder:text-muted-foreground/10"
              placeholder={t("chapterTitlePlaceholder")}
              aria-label={t("chapterTitlePlaceholder")}
            />
          </div>
          <div className="flex items-center gap-8">
            <div className="flex items-center gap-2.5 text-sm font-semibold text-muted-foreground/80 bg-muted/30 px-3 py-1.5 rounded-full border border-border/10">
              <Clock className="w-4 h-4 text-primary/40" aria-hidden="true" />
              <span className="tabular-nums">{formatLastSaved(lastSavedAt)}</span>
            </div>
            <button
              type="button"
              onClick={handleManualSave}
              className="flex items-center gap-2.5 px-7 py-2.5 bg-primary text-primary-foreground rounded-xl hover:opacity-90 active:scale-95 transition-all shadow-lg cursor-pointer font-bold text-sm tracking-wide"
            >
              <Save className="w-4 h-4" aria-hidden="true" />
              <span>{t("save")}</span>
            </button>
          </div>
        </div>
      )}

      {/* Focus mode: minimal ESC hint */}
      {focusMode && (
        <div className="absolute bottom-4 right-4 z-10 pointer-events-none">
          <kbd className="text-[0.625rem] px-2 py-1 rounded bg-muted/60 text-muted-foreground font-mono">
            {t("escKey")} — {t("exitFocus")}
          </kbd>
        </div>
      )}

      <div className="flex-1 flex overflow-hidden">
        {/* Editor area — clean, no parchment */}
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-4xl mx-auto">
            <EditorSurface
              novelId={novelId}
              chapter={activeChapter ?? null}
              autosaveInterval={autosaveInterval}
              onWordCountUpdate={handleWordCountUpdate}
            />
          </div>
        </main>

        {/* Right context panel — project AI settings */}
        {contextPanelOpen && !focusMode && <ContextPanel novelId={novelId} />}
      </div>

      {/* Status bar — hidden in focus mode */}
      {!focusMode && <StatusBar chapter={activeChapter ?? null} />}

      {/* Command palette */}
      <CommandPalette
        editor={editor}
        isOpen={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
        context={{
          toggleSidebar,
          toggleFocusMode,
          toggleContextPanel,
          saveChapter: handleManualSave,
          createChapter: () => {
            // Placeholder — will be implemented with WRITE-002
          },
        }}
      />

      {/* Name Generator modal */}
      <NameGeneratorModal
        projectId={novelId}
        isOpen={nameGeneratorOpen}
        onClose={() => setNameGeneratorOpen(false)}
      />
    </div>
  );
}
