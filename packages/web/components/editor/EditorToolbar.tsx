"use client";

import { Dices, Maximize2, PanelLeft, PanelRight } from "lucide-react";
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
  onOpenNameGenerator: () => void;
  sidebarOpen: boolean;
  panelOpen: boolean;
}

export function EditorToolbar({
  onToggleSidebar,
  onTogglePanel,
  onToggleFocus,
  onOpenNameGenerator,
  sidebarOpen,
  panelOpen,
}: EditorToolbarProps) {
  const t = useTranslations("editor");

  return (
    <div
      className="h-11 border-b border-[var(--color-border)] bg-[var(--color-bg-tertiary)] flex items-center px-4 gap-2 shrink-0"
      role="toolbar"
      aria-label="Editor toolbar"
    >
      {/* Left: sidebar toggle */}
      <div className="flex items-center gap-1 pr-3 border-r border-[var(--color-border)]">
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggleSidebar}
          aria-label={t("sidebar")}
          aria-pressed={sidebarOpen}
          title={`${t("sidebar")} (⌘\\)`}
          className={`text-[var(--color-text-secondary)] hover:bg-[var(--color-surface)] hover:text-[var(--color-text-primary)] ${sidebarOpen ? "bg-[var(--color-accent-light)]" : ""}`}
        >
          <PanelLeft size={18} />
        </Button>
      </div>

      {/* Center: AI tools */}
      <div className="flex-1 flex items-center justify-center">
        <div className="flex items-center gap-2 px-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={onOpenNameGenerator}
            aria-label={t("nameGenerator")}
            title={t("nameGenerator")}
            className="text-[var(--color-text-secondary)] hover:bg-[var(--color-surface)] hover:text-[var(--color-text-primary)] gap-1.5"
          >
            <Dices size={16} />
            <span className="text-[0.8125rem] hidden sm:inline">{t("nameGenerator")}</span>
          </Button>
          {AI_TOOLBAR_ACTIONS.length > 0 && (
            <div className="flex items-center gap-2 px-3 border-l border-[var(--color-border)]">
              {/* AI action buttons will appear here */}
            </div>
          )}
        </div>
      </div>

      {/* Right: panel toggle + focus mode — grouped in subtle pill */}
      <div className="flex items-center gap-1 ml-auto bg-[var(--color-surface)] rounded-lg px-1 py-0.5 border border-[var(--color-border)]/50">
        <Button
          variant="ghost"
          size="sm"
          onClick={onTogglePanel}
          aria-label={t("contextPanel")}
          aria-pressed={panelOpen}
          className={`text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)] ${panelOpen ? "bg-[var(--color-accent-light)]" : ""}`}
        >
          <PanelRight size={18} />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggleFocus}
          aria-label={t("focusMode")}
          title={`${t("focusMode")} (⌘⇧F)`}
          className="text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)]"
        >
          <Maximize2 size={18} />
        </Button>
        <span className="text-[0.625rem] text-[var(--color-text-tertiary)] hidden lg:inline pl-1">
          {t("commandPaletteHint")}
        </span>
      </div>
    </div>
  );
}
