"use client";

import { useTranslations } from "next-intl";

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
  const t = useTranslations("editor");

  return (
    <aside className="w-[var(--panel-width)] border-l border-[var(--color-border)] bg-[var(--color-surface)] flex flex-col shrink-0 overflow-hidden">
      <div className="px-4 py-3 border-b border-[var(--color-border)] shrink-0">
        <span className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">
          {t("contextPanel")}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {/* AI feature sections will appear here */}
        <p className="text-sm text-[var(--color-text-tertiary)] text-center py-8 px-4">
          {t("contextPanelEmpty")}
        </p>
      </div>
    </aside>
  );
}
