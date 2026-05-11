"use client"

import { useState } from "react"
import { useTranslations } from "next-intl"
import { useWizardStore } from "@/lib/stores/wizardStore"
import { setupApi } from "@/lib/api/client"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import type { StarterContent, DemoProjectInfo } from "@/types"

const DEMO_OPTIONS: StarterContent[] = ["demo_fantasy", "demo_scifi", "demo_german"]

interface StarterCardProps {
  id: StarterContent
  title: string
  description: string
  meta?: string
  selected: boolean
  onSelect: () => void
}

function StarterCard({ title, description, meta, selected, onSelect }: StarterCardProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`starter-card ${selected ? "starter-card--selected" : ""}`}
      aria-pressed={selected}
    >
      <div className="starter-card-title">{title}</div>
      <div className="starter-card-desc">{description}</div>
      {meta && <div className="starter-card-meta">{meta}</div>}

      <style jsx>{`
        .starter-card {
          text-align: left;
          padding: var(--space-4);
          border: 2px solid var(--color-border);
          border-radius: var(--radius-lg);
          background: var(--color-surface);
          cursor: pointer;
          transition: border-color 0.15s, background 0.15s;
          width: 100%;
        }
        .starter-card:hover { border-color: var(--color-accent-muted); }
        .starter-card--selected {
          border-color: var(--color-accent);
          background: var(--color-accent-light);
        }
        .starter-card-title { font-weight: 600; margin-bottom: var(--space-1); }
        .starter-card-desc { font-size: 0.875rem; color: var(--color-text-secondary); }
        .starter-card-meta {
          font-size: 0.75rem;
          color: var(--color-text-tertiary);
          margin-top: var(--space-2);
        }
      `}</style>
    </button>
  )
}

export function WizardStep3({
  onNext,
  onBack,
}: {
  onNext: () => void
  onBack: () => void
}) {
  const t = useTranslations("wizard.step3")
  const tCommon = useTranslations("common")
  const { updateStep3, state } = useWizardStore()

  const [selected, setSelected] = useState<StarterContent>(state.starter)
  const [importPath, setImportPath] = useState(state.import_path || "")
  const [demoInfo, setDemoInfo] = useState<Record<string, DemoProjectInfo>>({})
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSelectDemo = async (starter: StarterContent) => {
    setSelected(starter)
    setError(null)
    if (DEMO_OPTIONS.includes(starter) && !demoInfo[starter]) {
      try {
        const result = await setupApi.validateStep3({ starter })
        if (result.demo_info) {
          setDemoInfo((prev) => ({ ...prev, [starter]: result.demo_info! }))
        }
      } catch {
        // Non-critical — info is display-only
      }
    }
  }

  const handleNext = async () => {
    setIsSubmitting(true)
    setError(null)
    try {
      await setupApi.validateStep3({
        starter: selected,
        import_path: selected === "import" ? importPath : null,
      })
      updateStep3({
        starter: selected,
        import_path: selected === "import" ? importPath : null,
      })
      onNext()
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || "Validation failed")
    } finally {
      setIsSubmitting(false)
    }
  }

  const formatMeta = (info: DemoProjectInfo) =>
    `${info.chapter_count} chapters · ${info.character_count} characters · ${info.word_count.toLocaleString()} words`

  return (
    <div className="step">
      <div className="step-header">
        <h2 className="step-title">{t("title")}</h2>
        <p className="step-description">{t("description")}</p>
      </div>

      <div className="starter-grid">
        <StarterCard
          id="blank"
          title={t("blank")}
          description={t("blankDescription")}
          selected={selected === "blank"}
          onSelect={() => handleSelectDemo("blank")}
        />

        {DEMO_OPTIONS.map((id) => {
          const info = demoInfo[id]
          return (
            <StarterCard
              key={id}
              id={id}
              title={info?.title || id.replace("demo_", "Demo ")}
              description={info?.description || ""}
              meta={info ? formatMeta(info) : undefined}
              selected={selected === id}
              onSelect={() => handleSelectDemo(id)}
            />
          )
        })}

        <StarterCard
          id="import"
          title={t("import")}
          description={t("importDescription")}
          selected={selected === "import"}
          onSelect={() => handleSelectDemo("import")}
        />
      </div>

      {selected === "import" && (
        <Input
          label={t("importPath")}
          value={importPath}
          onChange={(e) => setImportPath(e.target.value)}
          placeholder="/path/to/your/manuscript"
          autoFocus
        />
      )}

      {error && <p className="step-error">{error}</p>}

      <div className="step-actions">
        <Button type="button" variant="secondary" onClick={onBack}>
          ← {tCommon("back")}
        </Button>
        <Button onClick={handleNext} loading={isSubmitting}>
          {tCommon("next")} →
        </Button>
      </div>

      <style jsx>{`
        .starter-grid {
          display: flex;
          flex-direction: column;
          gap: var(--space-3);
        }
        .step-error {
          background: var(--color-error-light);
          color: var(--color-error);
          border-radius: var(--radius-md);
          padding: var(--space-3);
          font-size: 0.875rem;
        }
      `}</style>
    </div>
  )
}
