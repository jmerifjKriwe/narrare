"use client";

import { Clock, LayoutGrid, PanelRight, Save } from "lucide-react";
import { useTranslations } from "next-intl";

interface EditorHeaderProps {
  title: string;
  onTitleChange: (value: string) => void;
  lastSaved: string | null;
  onSave: () => void;
  storyboardOpen: boolean;
  toggleStoryboard: () => void;
  contextPanelOpen: boolean;
  toggleContextPanel: () => void;
}

export function EditorHeader({
  title,
  onTitleChange,
  lastSaved,
  onSave,
  storyboardOpen,
  toggleStoryboard,
  contextPanelOpen,
  toggleContextPanel,
}: EditorHeaderProps) {
  const t = useTranslations("studio");

  return (
    <div className="border-b border-border px-8 py-4 flex items-center justify-between bg-card">
      <input
        type="text"
        data-testid="chapter-title-input"
        value={title}
        onChange={(e) => onTitleChange(e.target.value)}
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
          data-testid="save-button"
          onClick={onSave}
          className="flex items-center gap-2 px-5 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity shadow-sm"
        >
          <Save className="w-4 h-4" />
          <span className="text-sm">{t("editor.save")}</span>
        </button>
      </div>
    </div>
  );
}
