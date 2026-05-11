"use client"

import { useState } from "react"
import { useTranslations } from "next-intl"
import { useWizardStore } from "@/lib/stores/wizardStore"
import { Button } from "@/components/ui/Button"
import type { StoryStructure, StoryTone } from "@/types"

interface SummaryRowProps {
  label: string
  value: string
}

function SummaryRow({ label, value }: SummaryRowProps) {
  return (
    <div className="summary-row">
      <span className="summary-label">{label}</span>
      <span className="summary-value">{value || "—"}</span>
      <style jsx>{`
        .summary-row {
          display: flex;
          justify-content: space-between;
          align-items: baseline;
          padding: var(--space-2) 0;
          border-bottom: 1px solid var(--color-border);
          font-size: 0.9375rem;
          gap: var(--space-4);
        }
        .summary-row:last-child { border-bottom: none; }
        .summary-label { color: var(--color-text-secondary); flex-shrink: 0; }
        .summary-value { color: var(--color-text-primary); font-weight: 500; text-align: right; word-break: break-word; }
      `}</style>
    </div>
  )
}

export function WizardStep5({
  onComplete,
  onBack,
}: {
  onComplete: () => Promise<void>
  onBack: () => void
}) {
  const t = useTranslations("wizard.step5")
  const tCommon = useTranslations("common")
  const tStructure = useTranslations("wizard.storyStructure")
  const tTone = useTranslations("wizard.tone")
  const { state } = useWizardStore()
  const [isCreating, setIsCreating] = useState(false)

  const handleComplete = async () => {
    setIsCreating(true)
    try {
      await onComplete()
    } finally {
      setIsCreating(false)
    }
  }

  const starterLabel: Record<string, string> = {
    blank: "Blank project",
    demo_fantasy: "Demo: Echoes of the Thornwall",
    demo_scifi: "Demo: Dead Signal",
    demo_german: "Demo: Im stillen Wald",
    import: `Import from ${state.import_path || "—"}`,
  }

  return (
    <div className="step">
      <div className="step-header">
        <h2 className="step-title">{t("title")}</h2>
        <p className="step-description">{t("description")}</p>
      </div>

      <div className="summary-sections">
        <div className="summary-section">
          <h3 className="summary-section-title">{t("project")}</h3>
          <SummaryRow label="Name" value={state.project_name} />
          <SummaryRow label="Language" value={state.language.toUpperCase()} />
          <SummaryRow
            label="Autosave"
            value={state.autosave_interval === 0 ? "Off" : `${state.autosave_interval}s`}
          />
        </div>

        <div className="summary-section">
          <h3 className="summary-section-title">{t("novel")}</h3>
          <SummaryRow label="Title" value={state.title} />
          {state.author && <SummaryRow label="Author" value={state.author} />}
          {state.genre && <SummaryRow label="Genre" value={state.genre} />}
          <SummaryRow label="Structure" value={tStructure(state.story_structure as StoryStructure)} />
          <SummaryRow label="Tone" value={tTone(state.tone as StoryTone)} />
        </div>

        <div className="summary-section">
          <h3 className="summary-section-title">{t("starter")}</h3>
          <SummaryRow label="Content" value={starterLabel[state.starter] || state.starter} />
        </div>

        <div className="summary-section">
          <h3 className="summary-section-title">{t("provider")}</h3>
          <SummaryRow label="Provider" value={state.provider} />
          <SummaryRow label="Model" value={state.model} />
        </div>
      </div>

      {isCreating && (
        <p className="creating-status">{t("creating")}</p>
      )}

      <div className="step-actions">
        <Button type="button" variant="secondary" onClick={onBack} disabled={isCreating}>
          ← {tCommon("back")}
        </Button>
        <Button onClick={handleComplete} loading={isCreating}>
          {tCommon("finish")} ✓
        </Button>
      </div>

      <style jsx>{`
        .summary-sections {
          display: flex;
          flex-direction: column;
          gap: var(--space-4);
        }
        .summary-section {
          background: var(--color-surface-raised);
          border-radius: var(--radius-lg);
          padding: var(--space-4);
        }
        .summary-section-title {
          font-size: 0.75rem;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: var(--color-text-tertiary);
          margin-bottom: var(--space-2);
        }
        .creating-status {
          text-align: center;
          color: var(--color-text-secondary);
          font-size: 0.9375rem;
          padding: var(--space-2);
        }
      `}</style>
    </div>
  )
}
