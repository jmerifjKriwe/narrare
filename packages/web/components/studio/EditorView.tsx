"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Clock, Database, LayoutGrid, PanelRight, Save, Sparkles, Wand2 } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { chaptersApi, volumesApi } from "@/lib/api/client";
import { writingApi } from "@/lib/api/generation";
import { useEditorStore } from "@/lib/stores/editorStore";
import { markdownToHtml } from "@/lib/utils";
import { BetaReaderPanel } from "./analysis/BetaReaderPanel";
import { BetaReaderTrigger } from "./analysis/BetaReaderTrigger";
import { CommandPalette } from "./editor/CommandPalette";
import type { CommandContext, CommandState } from "./editor/commands";
import { GenerationPanel } from "./editor/GenerationPanel";
import { GhostTextConfig } from "./editor/GhostTextConfig";
import { MetadataSidebar } from "./editor/MetadataSidebar";
import { SessionPanel } from "./editor/SessionPanel";
import { ExtractionPanel } from "./extraction/ExtractionPanel";
import { NameGeneratorModal } from "./generation/NameGeneratorModal";
import { StoryboardPanel } from "./planning/StoryboardPanel";
import { TipTapEditor } from "./TipTapEditor";
import {
  type StepStatus,
  WritingGraphStatus,
  type WritingStep,
} from "./writing/WritingGraphStatus";

interface EditorViewProps {
  novelId: string;
}

export function EditorView({ novelId }: EditorViewProps) {
  const t = useTranslations("studio");
  const locale = useLocale();
  const queryClient = useQueryClient();

  // Core state
  const activeChapterId = useEditorStore((s) => s.activeChapterId);
  const activeVolumeId = useEditorStore((s) => s.activeVolumeId);
  const editor = useEditorStore((s) => s.editor);
  const setSaveStatus = useEditorStore((s) => s.setSaveStatus);
  const toggleSidebar = useEditorStore((s) => s.toggleSidebar);
  const toggleFocusMode = useEditorStore((s) => s.toggleFocusMode);
  const toggleContextPanel = useEditorStore((s) => s.toggleContextPanel);
  const contextPanelOpen = useEditorStore((s) => s.contextPanelOpen);
  const storyboardOpen = useEditorStore((s) => s.storyboardOpen);
  const toggleStoryboard = useEditorStore((s) => s.toggleStoryboard);

  // Generation state
  const isGenerating = useEditorStore((s) => s.isGenerating);
  const activeRequestId = useEditorStore((s) => s.activeRequestId);
  const draftText = useEditorStore((s) => s.draftText);
  const sessionActive = useEditorStore((s) => s.sessionActive);
  const generationPanelOpen = useEditorStore((s) => s.generationPanelOpen);
  const setGenerating = useEditorStore((s) => s.setGenerating);
  const setActiveRequestId = useEditorStore((s) => s.setActiveRequestId);
  const setGenerationMode = useEditorStore((s) => s.setGenerationMode);
  const setDraftText = useEditorStore((s) => s.setDraftText);
  const setSessionActive = useEditorStore((s) => s.setSessionActive);
  const toggleGenerationPanel = useEditorStore((s) => s.toggleGenerationPanel);

  // Extraction state
  const extractionPanelOpen = useEditorStore((s) => s.extractionPanelOpen);
  const toggleExtractionPanel = useEditorStore((s) => s.toggleExtractionPanel);

  // Beta reader state
  const betaReaderPanelOpen = useEditorStore((s) => s.betaReaderPanelOpen);
  const toggleBetaReaderPanel = useEditorStore((s) => s.toggleBetaReaderPanel);

  // Compute writing graph status steps from current editor state
  const writingSteps: Array<{ id: WritingStep; status: StepStatus }> = useMemo(() => {
    const STEP_ORDER: WritingStep[] = [
      "plan_outline",
      "write_draft",
      "review_draft",
      "revise_draft",
      "finalize",
      "generate_summary",
    ];

    // When generation is active, show progress through pipeline steps
    if (isGenerating && activeChapterId) {
      return STEP_ORDER.map((id, idx) => {
        // First 2 steps completed, 3rd is current, rest pending as a basic heuristic
        if (idx < 2) return { id, status: "completed" as const };
        if (idx === 2) return { id, status: "current" as const };
        return { id, status: "pending" as const };
      });
    }

    // Default: all pending
    return STEP_ORDER.map((id) => ({ id, status: "pending" as const }));
  }, [isGenerating, activeChapterId]);

  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [wordCount, setWordCount] = useState(0);
  const [charCount, setCharCount] = useState(0);
  const [paragraphCount, setParagraphCount] = useState(0);
  const [sessionStartWordCount, setSessionStartWordCount] = useState(0);
  const [lastSaved, setLastSaved] = useState<string | null>(null);
  const [sessionMode, setSessionMode] = useState<"interactive_session" | "interview_assisted">(
    "interactive_session",
  );

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
      setTitle(chapter.title ?? "");
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
      // Get live content from TipTap editor (more reliable than React state)
      const htmlContent = editor?.getHTML() ?? content;

      // Save both title and content in parallel
      await Promise.all([
        chaptersApi.updateMeta(novelId, activeChapterId, { title }),
        chaptersApi.updateContent(novelId, activeChapterId, htmlContent),
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

  // -------------------------------------------------------------------------
  // Generation actions
  // -------------------------------------------------------------------------

  const handleDraftAccepted = useCallback(
    (text: string) => {
      if (editor) {
        editor.commands.insertContent(text);
      }
      setDraftText("");
      setGenerating(false);
      setActiveRequestId(null);
      // Trigger autosave after accepting draft
      const htmlContent = editor?.getHTML() ?? content;
      handleAutosave(htmlContent);
    },
    [editor, content, setDraftText, setGenerating, setActiveRequestId, handleAutosave],
  );

  const handleStartSession = useCallback(
    (mode: string) => {
      setGenerationMode(mode);
      setSessionMode(mode as "interactive_session" | "interview_assisted");
      setSessionActive(true);
      // Close generation panel if open
      if (generationPanelOpen) {
        toggleGenerationPanel();
      }
    },
    [setGenerationMode, setSessionActive, generationPanelOpen, toggleGenerationPanel],
  );

  const handleSessionClose = useCallback(() => {
    setSessionActive(false);
    setGenerationMode(null);
    setSessionMode("interactive_session");
  }, [setSessionActive, setGenerationMode]);

  const handleStartGeneration = useCallback(
    (mode: string) => {
      if (mode === "interactive_session" || mode === "interview_assisted") {
        handleStartSession(mode);
        return;
      }
      setGenerationMode(mode);
      toggleGenerationPanel();
    },
    [handleStartSession, setGenerationMode, toggleGenerationPanel],
  );

  const handleStopGeneration = useCallback(async () => {
    if (activeRequestId) {
      await writingApi.stopGeneration(activeRequestId);
    }
    setGenerating(false);
    setActiveRequestId(null);
  }, [activeRequestId, setGenerating, setActiveRequestId]);

  const handleAcceptDraft = useCallback(() => {
    if (draftText) {
      handleDraftAccepted(draftText);
    }
  }, [draftText, handleDraftAccepted]);

  const handleRejectDraft = useCallback(async () => {
    if (activeRequestId) {
      await writingApi.rejectDraft(activeRequestId);
    }
    setDraftText("");
    setGenerating(false);
    setActiveRequestId(null);
  }, [activeRequestId, setDraftText, setGenerating, setActiveRequestId]);

  // -------------------------------------------------------------------------
  // Command context & state
  // -------------------------------------------------------------------------

  const commandContext: CommandContext = useCallback(
    () => ({
      toggleSidebar,
      toggleFocusMode,
      toggleContextPanel,
      toggleStoryboard,
      saveChapter: () => void handleSave(),
      createChapter: () => {
        // TODO: Wire to chapter creation
      },
      startGeneration: handleStartGeneration,
      stopGeneration: handleStopGeneration,
      acceptDraft: handleAcceptDraft,
      rejectDraft: handleRejectDraft,
      toggleGenerationPanel,
      startExtend: (_length: "short" | "medium" | "long") => {
        // TODO: Wire to extend flow (ContinueButton handles this directly)
      },
      startRewrite: () => {
        // TODO: Wire to rewrite flow (TipTapEditor handles this directly via BubbleMenu)
      },
    }),
    [
      toggleSidebar,
      toggleFocusMode,
      toggleContextPanel,
      handleSave,
      handleStartGeneration,
      handleStopGeneration,
      handleAcceptDraft,
      handleRejectDraft,
      toggleGenerationPanel,
      toggleStoryboard,
    ],
  )();

  const commandState: CommandState = useMemo(
    () => ({
      isGenerating,
      hasDraft: draftText.length > 0,
      hasPendingAnnotation: false, // TODO: Wire to hasPendingMark(editor)
      hasSelection: false, // TODO: Wire to editor selection state
      selectionLength: 0, // TODO: Wire to editor selection length
    }),
    [isGenerating, draftText],
  );

  // -------------------------------------------------------------------------
  // Keyboard shortcuts
  // -------------------------------------------------------------------------

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

  // -------------------------------------------------------------------------
  // Sidebar priority: SessionPanel > GenerationPanel > BetaReaderPanel > MetadataSidebar
  // -------------------------------------------------------------------------

  const showSessionPanel = sessionActive && !!activeChapterId;
  const showGenerationPanel = generationPanelOpen && !!activeChapterId && !showSessionPanel;
  const showBetaReaderPanel =
    betaReaderPanelOpen && !!activeChapterId && !showSessionPanel && !showGenerationPanel;
  const showMetadataSidebar =
    contextPanelOpen && !showSessionPanel && !showGenerationPanel && !showBetaReaderPanel;

  // -------------------------------------------------------------------------
  // Render — no chapter selected
  // -------------------------------------------------------------------------

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

  // -------------------------------------------------------------------------
  // Render — main editor view
  // -------------------------------------------------------------------------

  return (
    <div className="flex-1 flex flex-col h-full bg-background">
      {/* Storyboard panel — full-width, above toolbar */}
      <StoryboardPanel novelId={novelId} />

      {/* Writing graph pipeline — progress indicator */}
      <WritingGraphStatus steps={writingSteps} />

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
            onClick={toggleStoryboard}
            className={`p-2 rounded-md hover:bg-accent transition-colors ${storyboardOpen ? "bg-accent" : ""}`}
            title={t("storyboard.toggleStoryboard")}
            aria-label={t("storyboard.toggleStoryboard")}
          >
            <LayoutGrid className="w-4 h-4" />
          </button>
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

      {/* Toolbar: formatting actions + AI tools */}
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
          <div className="w-px h-5 bg-border mx-1" />
          <button
            type="button"
            onClick={toggleGenerationPanel}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded hover:bg-accent transition-colors text-sm text-primary ${
              generationPanelOpen ? "bg-accent" : ""
            }`}
            title={t("editor.generate")}
          >
            <Wand2 className="w-3.5 h-3.5" />
            <span>{t("editor.generate")}</span>
          </button>
          <div className="w-px h-5 bg-border mx-1" />
          <button
            type="button"
            onClick={toggleExtractionPanel}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded hover:bg-accent transition-colors text-sm text-primary ${
              extractionPanelOpen ? "bg-accent" : ""
            }`}
            title={t("kb.extract")}
          >
            <Database className="w-3.5 h-3.5" />
            <span>{t("kb.extract")}</span>
          </button>
          <div className="w-px h-5 bg-border mx-1" />
          <BetaReaderTrigger />
          <div className="w-px h-5 bg-border mx-1" />
          <GhostTextConfig editor={editor} />
        </div>
      )}

      {/* Editor area + Side panels */}
      <div className="flex-1 flex min-h-0">
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-4xl mx-auto">
            <TipTapEditor
              content={content}
              onChange={setContent}
              onAutosave={handleAutosave}
              autosaveInterval={30_000}
              chapterId={activeChapterId ?? undefined}
              novelId={novelId}
            />
          </div>
        </div>
        {showSessionPanel && (
          <SessionPanel
            chapterId={activeChapterId}
            novelId={novelId}
            mode={sessionMode}
            onClose={handleSessionClose}
          />
        )}
        {showGenerationPanel && (
          <GenerationPanel
            novelId={novelId}
            chapterId={activeChapterId}
            chapterContent={content}
            onDraftAccepted={handleDraftAccepted}
            onClose={toggleGenerationPanel}
            onStartSession={handleStartSession}
          />
        )}
        {showMetadataSidebar && (
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
        {showBetaReaderPanel && (
          <BetaReaderPanel
            novelId={novelId}
            chapterIds={activeChapterId ? [activeChapterId] : []}
            onClose={toggleBetaReaderPanel}
          />
        )}
      </div>

      {/* Command Palette overlay */}
      <CommandPalette
        editor={editor}
        isOpen={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
        context={commandContext}
        commandState={commandState}
      />

      {/* Name Generator slide-in panel */}
      <NameGeneratorModal
        novelId={novelId}
        isOpen={nameGeneratorOpen}
        onClose={() => setNameGeneratorOpen(false)}
      />

      {/* Extraction panel — modal overlay */}
      {extractionPanelOpen && activeChapterId && (
        <ExtractionPanel
          novelId={novelId}
          chapterId={activeChapterId}
          onClose={toggleExtractionPanel}
          onApplied={() => {
            // Invalidate KB queries so the KB panel refreshes
            void queryClient.invalidateQueries({ queryKey: ["kb", novelId] });
          }}
        />
      )}
    </div>
  );
}
