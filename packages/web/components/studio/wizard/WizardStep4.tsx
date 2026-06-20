"use client";

import { useTranslations } from "next-intl";
import { PROVIDERS } from "@/lib/providers";
import { useWizardStore } from "@/lib/stores/wizardStore";
import { FallbackCatalogNotice } from "./FallbackCatalogNotice";
import { ModelSelector } from "./ModelSelector";
import { useProviderSetup } from "./useProviderSetup";

interface WizardStep4Props {
  onNext: () => void;
  onBack: () => void;
}

export function WizardStep4({ onNext, onBack }: WizardStep4Props) {
  const t = useTranslations("studio");
  const tCommon = useTranslations("common");
  const { updateStep4, state } = useWizardStore();

  const {
    provider,
    apiKey,
    ollamaUrl,
    zaiEndpoint,
    model,
    models,
    modelsLoading,
    validating,
    error,
    provenance,
    setProvider,
    setApiKey,
    setOllamaUrl,
    setZaiEndpoint,
    setModel,
    handleValidate,
  } = useProviderSetup(
    {
      provider: state.provider,
      api_key: state.api_key,
      ollama_url: state.ollama_url,
      zai_endpoint: state.zai_endpoint ?? "general",
      model: state.model,
    },
    (data) => {
      updateStep4(data);
      onNext();
    },
    t("wizard.step4.validationFailed"),
  );

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-xl font-semibold mb-1">{t("wizard.step4.title")}</h2>
        <p className="text-muted-foreground text-[0.9375rem]">{t("wizard.step4.description")}</p>
      </div>

      <div className="flex flex-col gap-5">
        <div>
          <label htmlFor="provider" className="block text-sm font-medium mb-1.5">
            {t("wizard.step4.provider")}
          </label>
          <select
            id="provider"
            value={provider}
            onChange={(e) => setProvider(e.target.value as typeof provider)}
            className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
          >
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </div>

        {provider === "ollama" ? (
          <div>
            <label htmlFor="ollama_url" className="block text-sm font-medium mb-1.5">
              {t("wizard.step4.ollamaUrl")}
            </label>
            <input
              id="ollama_url"
              type="text"
              value={ollamaUrl}
              onChange={(e) => setOllamaUrl(e.target.value)}
              placeholder="http://localhost:11434"
              className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
            />
          </div>
        ) : (
          <div>
            <label htmlFor="api_key" className="block text-sm font-medium mb-1.5">
              {t("wizard.step4.apiKey")}
            </label>
            <input
              id="api_key"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={t("wizard.step4.apiKeyPlaceholder")}
              autoComplete="off"
              className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
            />
          </div>
        )}

        {provider === "zai" && (
          <div>
            <label htmlFor="zai_endpoint" className="block text-sm font-medium mb-1.5">
              {t("wizard.step4.zaiEndpoint")}
            </label>
            <select
              id="zai_endpoint"
              value={zaiEndpoint}
              onChange={(e) => setZaiEndpoint(e.target.value)}
              className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
            >
              <option value="general">{t("wizard.step4.zaiGeneral")}</option>
              <option value="coding">{t("wizard.step4.zaiCoding")}</option>
            </select>
          </div>
        )}

        <ModelSelector
          model={model}
          models={models}
          modelsLoading={modelsLoading}
          setModel={setModel}
        />

        {validating && (
          <p className="text-sm text-blue-600 dark:text-blue-400">{t("wizard.step4.validating")}</p>
        )}

        <FallbackCatalogNotice provenance={provenance} />

        {error && (
          <p className="bg-destructive/10 text-destructive rounded-lg p-3 text-sm">{error}</p>
        )}
      </div>

      <div className="flex justify-end gap-3 mt-4">
        <button
          type="button"
          onClick={onBack}
          data-testid="wizard-back"
          className="px-6 py-2 bg-muted rounded-md hover:bg-accent transition-colors text-sm"
        >
          ← {tCommon("back")}
        </button>
        <button
          type="button"
          onClick={handleValidate}
          disabled={validating || !model}
          data-testid="wizard-next"
          className="px-6 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity text-sm disabled:opacity-50"
        >
          {validating ? `${tCommon("next")}…` : `${tCommon("next")} →`}
        </button>
      </div>
    </div>
  );
}
