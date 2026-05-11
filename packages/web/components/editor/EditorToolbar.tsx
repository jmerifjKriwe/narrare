"use client"

import { useTranslations } from "next-intl"
import { PanelLeft, PanelRight, Maximize2 } from "lucide-react"
import { Button } from "@/components/ui/Button"

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
const AI_TOOLBAR_ACTIONS: never[] = []

interface EditorToolbarProps {
  onToggleSidebar: () => void
  onTogglePanel: () => void
  onToggleFocus: () => void
  sidebarOpen: boolean
  panelOpen: boolean
}

export function EditorToolbar({
  onToggleSidebar,
  onTogglePanel,
  onToggleFocus,
  sidebarOpen,
  panelOpen,
}: EditorToolbarProps) {
  const t = useTranslations("editor")

  return (
    <div className="toolbar" role="toolbar" aria-label="Editor toolbar">
      {/* Left: sidebar toggle */}
      <div className="toolbar-group">
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
      <div className="toolbar-center">
        {AI_TOOLBAR_ACTIONS.length > 0 && (
          <div className="toolbar-group toolbar-group--ai">
            {/* AI action buttons will appear here */}
          </div>
        )}
      </div>

      {/* Right: panel toggle + focus mode */}
      <div className="toolbar-group toolbar-group--right">
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

      <style jsx>{`
        .toolbar {
          height: 44px;
          border-bottom: 1px solid var(--color-border);
          background: var(--color-surface);
          display: flex;
          align-items: center;
          padding: 0 var(--space-3);
          gap: var(--space-2);
          flex-shrink: 0;
        }
        .toolbar-group {
          display: flex;
          align-items: center;
          gap: var(--space-1);
        }
        .toolbar-center {
          flex: 1;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .toolbar-group--right { margin-left: auto; }
        .toolbar-group--ai {
          gap: var(--space-2);
          padding: 0 var(--space-3);
          border-left: 1px solid var(--color-border);
          border-right: 1px solid var(--color-border);
        }
      `}</style>
    </div>
  )
}
