"use client";

import { Maximize2, PanelLeft, PanelRight } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/Button";

// ============================================================
// AI ACTION SLOT REGISTRY
//
// AI features register toolbar actions here when implemented.
// At MVP: empty. Pattern:
//
// import { registerToolbarAction } from "./toolbarRegistry"
// registerToolbarAction({
//   id: "write-new-chapter",
//   icon: PenLine,
//   label: t("toolbar.writeChapter"),
//   handler: () => openWriteChapterPanel(),
//   feature: "WRITE-002",
// })
// ============================================================
const AI_TOOLBAR_ACTIONS: never[] = [];

interface EditorToolbarProps {
  onToggleSidebar: () => void;
  onTogglePanel: () => void;
  onToggleFocus: () => void;
  sidebarOpen: boolean;
  panelOpen: boolean;
}

export function EditorToolbar({
  onToggleSidebar,
  onTogglePanel,
  onToggleFocus,
  sidebarOpen,
  panelOpen,
}: EditorToolbarProps) {
  const t = useTranslations("editor");

  return (
    <div
      className="h-11 border-b border-[var(--color-border)] bg-[var(--color-surface)] flex items-center px-3 gap-2 shrink-0"
      role="toolbar"
      aria-label="Editor toolbar"
    >
      {/* Left: sidebar toggle */}
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggleSidebar}
          aria-label={t("sidebar")}
          aria-pressed={sidebarOpen}
          title={`${t("sidebar")} (⌘\\)`}
        >
          <PanelLeft size={16} />
        </Button>
      </div>

      {/* Center: AI action slots — populated by AI features */}
      <div className="flex-1 flex items-center justify-center">
        {AI_TOOLBAR_ACTIONS.length > 0 && (
          <div className="flex items-center gap-2 px-3 border-l border-r border-[var(--color-border)]">
            {/* AI action buttons will appear here */}
          </div>
        )}
      </div>

      {/* Right: panel toggle + focus mode */}
      <div className="flex items-center gap-1 ml-auto">
        <Button
          variant="ghost"
          size="sm"
          onClick={onTogglePanel}
          aria-label={t("contextPanel")}
          aria-pressed={panelOpen}
        >
          <PanelRight size={16} />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggleFocus}
          aria-label={t("focusMode")}
          title={`${t("focusMode")} (⌘⇧F)`}
        >
          <Maximize2 size={16} />
        </Button>
      </div>
    </div>
  );
}
