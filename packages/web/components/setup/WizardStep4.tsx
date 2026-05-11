"use client"

import { useState, useEffect } from "react"
import { useTranslations } from "next-intl"
import { useWizardStore } from "@/lib/stores/wizardStore"
import { setupApi } from "@/lib/api/client"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Select } from "@/components/ui/Select"
import type { AIProvider } from "@/types"

const PROVIDERS: { value: AIProvider; label: string }[] = [
  { value: "anthropic", label: "Anthropic" },
  { value: "openai", label: "OpenAI" },
  { value: "google", label: "Google AI" },
  { value: "groq", label: "Groq" },
  { value: "ollama", label: "Ollama (local)" },
  { value: "openrouter", label: "OpenRouter" },
  { value: "zai", label: "Z.AI" },
]

export function WizardStep4({
  onNext,
  onBack,
}: {
  onNext: () => void
  onBack: () => void
}) {
  const t = useTranslations("wizard.step4")
  const tCommon = useTranslations("common")
  const { updateStep4, state } = useWizardStore()

  const [provider, setProvider] = useState<AIProvider>(state.provider)
  const [apiKey, setApiKey] = useState(state.api_key)
  const [ollamaUrl, setOllamaUrl] = useState(state.ollama_url)
  const [model, setModel] = useState(state.model)
  const [models, setModels] = useState<{ value: string; label: string }[]>([])
  const [modelsLoading, setModelsLoading] = useState(false)
  const [validating, setValidating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Load models when provider or key changes
  useEffect(() => {
    const key = apiKey.trim()
    if (provider === "ollama" || key.length > 8) {
      loadModels()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [provider, apiKey, ollamaUrl])

  const loadModels = async () => {
    setModelsLoading(true)
    setModels([])
    setModel("")
    try {
      const result = await setupApi.getProviderModels(provider, apiKey, ollamaUrl)
      const opts = result.models.map((m) => ({ value: m.id, label: m.name }))
      setModels(opts)
      if (opts.length > 0 && !model) setModel(opts[0].value)
    } catch {
      // Fallback — still show empty list, user can type manually
    } finally {
      setModelsLoading(false)
    }
  }

  const handleNext = async () => {
    setError(null)
    setValidating(true)
    try {
      await setupApi.validateStep4({
        provider,
        api_key: apiKey,
        model,
        ollama_url: ollamaUrl,
      })
      updateStep4({ provider, api_key: apiKey, model, ollama_url: ollamaUrl })
      onNext()
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || t("validationFailed"))
    } finally {
      setValidating(false)
    }
  }

  return (
    <div className="step">
      <div className="step-header">
        <h2 className="step-title">{t("title")}</h2>
        <p className="step-description">{t("description")}</p>
      </div>

      <div className="step-form">
        <Select
          label={t("provider")}
          value={provider}
          onChange={(e) => setProvider(e.target.value as AIProvider)}
          options={PROVIDERS}
        />

        {provider === "ollama" ? (
          <Input
            label={t("ollamaUrl")}
            value={ollamaUrl}
            onChange={(e) => setOllamaUrl(e.target.value)}
            placeholder="http://localhost:11434"
          />
        ) : (
          <Input
            label={t("apiKey")}
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={t("apiKeyPlaceholder")}
            autoComplete="off"
          />
        )}

        {modelsLoading ? (
          <p className="models-loading">{t("modelLoading")}</p>
        ) : models.length > 0 ? (
          <Select
            label={t("model")}
            value={model}
            onChange={(e) => setModel(e.target.value)}
            options={models}
            placeholder={t("modelPlaceholder")}
          />
        ) : (
          <Input
            label={t("model")}
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder={t("modelPlaceholder")}
          />
        )}

        {validating && (
          <p className="validation-status">{t("validating")}</p>
        )}

        {error && (
          <p className="step-error">{error}</p>
        )}
      </div>

      <div className="step-actions">
        <Button type="button" variant="secondary" onClick={onBack}>
          ← {tCommon("back")}
        </Button>
        <Button
          onClick={handleNext}
          loading={validating}
          disabled={!model}
        >
          {tCommon("next")} →
        </Button>
      </div>

      <style jsx>{`
        .models-loading {
          font-size: 0.875rem;
          color: var(--color-text-secondary);
          padding: var(--space-2);
        }
        .validation-status {
          font-size: 0.875rem;
          color: var(--color-info);
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
