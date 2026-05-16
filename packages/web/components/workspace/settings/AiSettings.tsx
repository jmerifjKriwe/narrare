"use client";

import { Cpu, Sparkles, MessageSquare } from "lucide-react";
import { useTranslations } from "next-intl";
import { PromptSettings } from "@/components/settings/PromptSettings";

export function AiSettings() {
  const t = useTranslations("settings");

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-2xl mb-2">{t("ai")}</h2>
        <p className="text-sm text-muted-foreground">
          {t("aiDescription")}
        </p>
      </div>

      <div className="space-y-4">
        {/* Provider card — simplified design-based UI */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center flex-shrink-0">
              <Cpu className="w-5 h-5" />
            </div>
            <div className="flex-1">
              <h3 className="mb-1 font-medium">{t("providers")}</h3>
              <p className="text-sm text-muted-foreground mb-4">
                {t("providersDescription")}
              </p>
              <select
                className="w-full px-4 py-2 bg-background border border-border rounded-md focus:ring-1 focus:ring-ring transition-shadow"
                aria-label={t("providers")}
              >
                <option>OpenAI</option>
                <option>Anthropic (Claude)</option>
                <option>Google (Gemini)</option>
                <option>Local (Ollama)</option>
              </select>
              <div className="mt-4">
                <label className="block text-sm font-medium mb-2" htmlFor="ai-api-key">
                  {t("apiKeyLabel")}
                </label>
                <input
                  id="ai-api-key"
                  type="password"
                  placeholder={t("apiKeyPlaceholder")}
                  className="w-full px-4 py-2 bg-background border border-border rounded-md focus:ring-1 focus:ring-ring transition-shadow"
                />
                <p className="text-xs text-muted-foreground mt-2">
                  {t("apiKeySecureNote")}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Models card — simplified design-based UI */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center flex-shrink-0">
              <Sparkles className="w-5 h-5" />
            </div>
            <div className="flex-1">
              <h3 className="mb-1 font-medium">{t("models")}</h3>
              <p className="text-sm text-muted-foreground mb-4">
                {t("modelsDescription")}
              </p>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2" htmlFor="model-rephrase">
                    {t("modelCategoryRephrase")}
                  </label>
                  <select
                    id="model-rephrase"
                    className="w-full px-4 py-2 bg-background border border-border rounded-md focus:ring-1 focus:ring-ring transition-shadow"
                  >
                    <option>gpt-4-turbo</option>
                    <option>gpt-3.5-turbo</option>
                    <option>claude-3-opus</option>
                    <option>claude-3-sonnet</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2" htmlFor="model-worldbuilding">
                    {t("modelCategoryWorldbuilding")}
                  </label>
                  <select
                    id="model-worldbuilding"
                    className="w-full px-4 py-2 bg-background border border-border rounded-md focus:ring-1 focus:ring-ring transition-shadow"
                  >
                    <option>gpt-4-turbo</option>
                    <option>gpt-3.5-turbo</option>
                    <option>claude-3-opus</option>
                    <option>claude-3-sonnet</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2" htmlFor="model-analysis">
                    {t("modelCategoryAnalysis")}
                  </label>
                  <select
                    id="model-analysis"
                    className="w-full px-4 py-2 bg-background border border-border rounded-md focus:ring-1 focus:ring-ring transition-shadow"
                  >
                    <option>gpt-4-turbo</option>
                    <option>gpt-3.5-turbo</option>
                    <option>claude-3-opus</option>
                    <option>claude-3-sonnet</option>
                  </select>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* System Prompts card — embeds existing PromptSettings */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center flex-shrink-0">
              <MessageSquare className="w-5 h-5" />
            </div>
            <div className="flex-1">
              <h3 className="mb-1 font-medium">{t("prompts")}</h3>
              <p className="text-sm text-muted-foreground mb-4">
                {t("promptsDescription")}
              </p>
              {/* Embed the full PromptSettings component — it uses TanStack Query */}
              <PromptSettings />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
