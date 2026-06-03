"use client";

import type { Editor } from "@tiptap/react";
import { Database, Sparkles, Wand2 } from "lucide-react";
import { useTranslations } from "next-intl";

import { BetaReaderTrigger } from "../analysis/BetaReaderTrigger";
import { ConsistencyTrigger } from "../analysis/ConsistencyTrigger";
import { POVTrigger } from "../analysis/POVTrigger";
import { ReadabilityTrigger } from "../analysis/ReadabilityTrigger";
import { SentimentTrigger } from "../analysis/SentimentTrigger";
import { GhostTextConfig } from "../editor/GhostTextConfig";

interface EditorToolbarProps {
  editor: Editor;
  generationPanelOpen: boolean;
  toggleGenerationPanel: () => void;
  extractionPanelOpen: boolean;
  toggleExtractionPanel: () => void;
  onOpenNameGenerator: () => void;
}

export function EditorToolbar({
  editor,
  generationPanelOpen,
  toggleGenerationPanel,
  extractionPanelOpen,
  toggleExtractionPanel,
  onOpenNameGenerator,
}: EditorToolbarProps) {
  const t = useTranslations("studio");

  return (
    <div className="border-b border-border px-8 py-2 bg-card flex items-center gap-1">
      {/* Formatting buttons */}
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

      {/* AI tools */}
      <div className="w-px h-5 bg-border mx-1" />
      <button
        type="button"
        onClick={onOpenNameGenerator}
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

      {/* Analysis triggers */}
      <div className="w-px h-5 bg-border mx-1" />
      <BetaReaderTrigger />
      <SentimentTrigger />
      <ConsistencyTrigger />
      <ReadabilityTrigger />
      <POVTrigger />

      {/* Ghost text config */}
      <div className="w-px h-5 bg-border mx-1" />
      <GhostTextConfig editor={editor} />
    </div>
  );
}
