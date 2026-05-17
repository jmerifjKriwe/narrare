"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Clock, PanelRight, Save, Sparkles } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import { chaptersApi, volumesApi } from "@/lib/api/client";
import { useEditorStore } from "@/lib/stores/editorStore";
import { markdownToHtml } from "@/lib/utils";
import { CommandPalette } from "./editor/CommandPalette";
import type { CommandContext } from "./editor/commands";
import { MetadataSidebar } from "./editor/MetadataSidebar";
import { NameGeneratorModal } from "./generation/NameGeneratorModal";
import { TipTapEditor } from "./TipTapEditor";

interface EditorViewProps {
  novelId: string;
}

export function EditorView({ novelId }: EditorViewProps) {
  const t = useTranslations("studio");
  const locale = useLocale();
  const queryClient = useQueryClient();

  const activeChapterId = useEditorStore((s) => s.activeChapterId);
  const activeVolumeId = useEditorStore((s) => s.activeVolumeId);
  const editor = useEditorStore((s) => s.editor);
  const setSaveStatus = useEditorStore((s) => s.setSaveStatus);
  const toggleSidebar = useEditorStore((s) => s.toggleSidebar);
  const toggleFocusMode = useEditorStore((s) => s.toggleFocusMode);
  const toggleContextPanel = useEditorStore((s) => s.toggleContextPanel);

  const contextPanelOpen = useEditorStore((s) => s.contextPanelOpen);

  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [wordCount, setWordCount] = useState(0);
  const [charCount, setCharCount] = useState(0);
  const [paragraphCount, setParagraphCount] = useState(0);
  const [sessionStartWordCount, setSessionStartWordCount] = useState(0);
  const [lastSaved, setLastSaved] = useState<string | null>(null);

  // Track last chapter ID for session start reset
  const prevChapterIdRef = useRef<string | null>(null);

  // Command palette state
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);

  // Name generator modal state
  const [nameGeneratorOpen, setNameGeneratorOpen] = useState(false);

  // Fetch active chapter content
  const { data: chapter, isLoading } = useQuery({
    queryKey: ["novels", novelId, "chapters", activeChapterId],
    queryFn: () => chaptersApi.get(novelId, activeChapterId!),
    enabled: !!activeChapterId,
  });

  // Fetch all chapters for novel (deduplicated — also fetched by Sidebar)
  const { data: chapters = [] } = useQuery({
    queryKey: ["novels", novelId, "chapters", activeVolumeId],
    queryFn: () => chaptersApi.list(novelId, activeVolumeId ?? undefined),
    enabled: !!novelId,
  });

  // Fetch active volume stats when a volume is selected
  const { data: volumeStats } = useQuery({
    queryKey: ["novels", novelId, "volumes", activeVolumeId, "stats"],
    queryFn: () => volumesApi.getStats(novelId, activeVolumeId!),
    enabled: !!novelId && !!activeVolumeId,
  });

  // Sync title and content from API data
  useEffect(() => {
    if (chapter) {
      setTitle(chapter.title);
      setContent(markdownToHtml(chapter.content || ""));
    }
  }, [chapter]);

  // Track session start word count (resets only when chapter changes)
  useEffect(() => {
    if (chapter && chapter.id !== prevChapterIdRef.current) {
      prevChapterIdRef.current = chapter.id;
      setSessionStartWordCount(chapter.word_count);
    }
  }, [chapter]);

  // Compute word, character, and paragraph counts
  useEffect(() => {
    const text = content.replace(/<[^>]*>/g, "");
    const words = text
      .trim()
      .split(/\s+/)
      .filter((w) => w.length > 0).length;
    const chars = text.length;
    const paragraphs = (content.match(/<p[\s>]/g) || []).length || 1;
    setWordCount(words);
    setCharCount(chars);
    setParagraphCount(paragraphs);
  }, [content]);

  const handleSave = useCallback(async () => {
    if (!activeChapterId) return;

    setSaveStatus("saving");
    try {
      // Always save title via meta endpoint
      await chaptersApi.updateMeta(novelId, activeChapterId, { title });

      // Save content — prefer autosave extension's forceSave, fallback to direct API
      const autosaveExt = editor?.extensionManager.extensions.find(
        (ext) => ext.name === "autosave",
      );
      if (autosaveExt) {
        const storage = autosaveExt.storage as { forceSave: () => Promise<void> };
        await storage.forceSave();
      } else {
        await chaptersApi.updateContent(novelId, activeChapterId, content);
      }

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
  }, [activeChapterId, editor, novelId, content, title, locale, setSaveStatus, queryClient]);

  // Autosave handler for TipTapEditor
  const handleAutosave = useCallback(
    async (htmlContent: string) => {
      if (!activeChapterId) return;
      setSaveStatus("saving");
      try {
        await Promise.all([
          chaptersApi.updateContent(novelId, activeChapterId, htmlContent),
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
    },
    [activeChapterId, novelId, title, locale, setSaveStatus, queryClient],
  );

  // Command context for CommandPalette
  const commandContext: CommandContext = useCallback(
    () => ({
      toggleSidebar,
      toggleFocusMode,
      toggleContextPanel,
      saveChapter: () => void handleSave(),
      createChapter: () => {
        // TODO: Wire to chapter creation
      },
    }),
    [toggleSidebar, toggleFocusMode, toggleContextPanel, handleSave],
  )();

  // Global keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Cmd/Ctrl+K → Command Palette
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCommandPaletteOpen((prev) => !prev);
      }
      // Cmd/Ctrl+S → Save
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        handleSave();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [handleSave]);

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
            onClick={toggleContextPanel}
            className={`p-2 rounded-md hover:bg-accent transition-colors ${contextPanelOpen ? "bg-accent" : ""}`}
            title={t("metadataSidebar.toggle")}
            aria-label={t("metadataSidebar.toggle")}
          >
            <PanelRight className="w-4 h-4" />
          </button>
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

      {/* Toolbar: formatting actions + AI tools (new features go here) */}
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
          <div className="w-px h-5 bg-border mx-1" />
          <button
            type="button"
            onClick={() => setNameGeneratorOpen(true)}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded hover:bg-accent transition-colors text-sm text-primary"
            title={t("editor.nameGenerator")}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>{t("editor.nameGenerator")}</span>
          </button>
        </div>
      )}

      {/* Editor area + Metadata Sidebar */}
      <div className="flex-1 flex min-h-0">
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-4xl mx-auto">
            <TipTapEditor
              content={content}
              onChange={setContent}
              onAutosave={handleAutosave}
              autosaveInterval={30_000}
            />
          </div>
        </div>
        {contextPanelOpen && (
          <MetadataSidebar
            wordCount={wordCount}
            charCount={charCount}
            paragraphCount={paragraphCount}
            chapter={chapter ?? null}
            chapters={chapters}
            sessionStartWordCount={sessionStartWordCount}
            activeVolumeStats={volumeStats ?? null}
          />
        )}
      </div>

      {/* Command Palette overlay */}
      <CommandPalette
        editor={editor}
        isOpen={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
        context={commandContext}
      />

      {/* Name Generator slide-in panel */}
      <NameGeneratorModal
        novelId={novelId}
        isOpen={nameGeneratorOpen}
        onClose={() => setNameGeneratorOpen(false)}
      />
    </div>
  );
}
