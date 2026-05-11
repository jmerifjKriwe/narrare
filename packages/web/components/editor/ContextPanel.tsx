"use client"

import { useTranslations } from "next-intl"

// ============================================================
// CONTEXT PANEL — AI feature sections register here.
//
// At MVP: empty shell. Pattern for future AI features:
//
// import { registerContextSection } from "./contextRegistry"
// registerContextSection({
//   id: "inline-suggestions",
//   title: t("panel.suggestions"),
//   component: InlineSuggestionsPanel,
//   feature: "WRITE-007",
// })
// ============================================================

export function ContextPanel() {
  const t = useTranslations("editor")

  return (
    <aside className="context-panel">
      <div className="context-panel-header">
        <span className="context-panel-title">{t("contextPanel")}</span>
      </div>

      <div className="context-panel-body">
        {/* AI feature sections will appear here */}
        <p className="context-panel-empty">
          AI features will appear here
        </p>
      </div>

      <style jsx>{`
        .context-panel {
          width: var(--panel-width);
          border-left: 1px solid var(--color-border);
          background: var(--color-surface);
          display: flex;
          flex-direction: column;
          flex-shrink: 0;
          overflow: hidden;
        }
        .context-panel-header {
          padding: var(--space-3) var(--space-4);
          border-bottom: 1px solid var(--color-border);
          flex-shrink: 0;
        }
        .context-panel-title {
          font-size: 0.75rem;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: var(--color-text-tertiary);
        }
        .context-panel-body {
          flex: 1;
          overflow-y: auto;
          padding: var(--space-4);
        }
        .context-panel-empty {
          font-size: 0.875rem;
          color: var(--color-text-tertiary);
          text-align: center;
          padding: var(--space-8) var(--space-4);
        }
      `}</style>
    </aside>
  )
}
