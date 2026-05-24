"use client";

import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import type { UserAiSettings, UserProvider } from "@/types";

// --- Types ---

interface DefaultModelSectionProps {
  readonly aiSettings: UserAiSettings | undefined;
  readonly providers: UserProvider[];
  readonly modelsData: { models: { id: string; name: string }[] } | undefined;
  readonly modelsLoading: boolean;
  readonly onProviderChange: (providerId: string) => void;
  readonly onModelChange: (modelId: string) => void;
}

// --- Component ---

export function DefaultModelSection({
  aiSettings,
  providers,
  modelsData,
  modelsLoading,
  onProviderChange,
  onModelChange,
}: DefaultModelSectionProps) {
  const t = useTranslations("studio");

  return (
    <div className="bg-card border border-border rounded-lg p-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
          <span className="text-lg">{"\uD83C\uDFAF"}</span>
        </div>
        <div>
          <h3 className="font-medium">{t("settings.ai.defaultModel")}</h3>
        </div>
      </div>
      <div className="space-y-4 ml-15">
        <div className="flex items-center justify-between">
          <span className="text-sm">{t("settings.ai.providerName")}</span>
          <select
            value={aiSettings?.default_provider_id ?? ""}
            onChange={(e) => onProviderChange(e.target.value)}
            className="px-4 py-2 bg-background border border-border rounded-md text-sm"
          >
            <option value="">{t("settings.ai.noneSelected")}</option>
            {providers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.provider_name}
              </option>
            ))}
          </select>
        </div>
        <div className="h-px bg-border" />
        <div className="flex items-center justify-between">
          <span className="text-sm">{t("settings.ai.defaultModel")}</span>
          {modelsLoading ? (
            <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
          ) : (
            <select
              value={aiSettings?.default_model ?? ""}
              onChange={(e) => onModelChange(e.target.value)}
              disabled={!aiSettings?.default_provider_id}
              className="px-4 py-2 bg-background border border-border rounded-md text-sm disabled:opacity-50"
            >
              <option value="">{t("settings.ai.selectProviderFirst")}</option>
              {modelsData?.models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>
    </div>
  );
}
