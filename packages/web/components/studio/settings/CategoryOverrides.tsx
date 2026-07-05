"use client";

import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import type { IntentCategory, ModelOverride, UserProvider } from "@/types";

// --- Static config ---

const CATEGORY_VALUES: IntentCategory[] = [
  "writing",
  "analysis",
  "kb",
  "planning",
  "extraction",
  "chat",
  "research",
];

const CATEGORY_LABEL_KEYS: Record<IntentCategory, string> = {
  writing: "writing",
  analysis: "analysis",
  kb: "knowledgeBase",
  planning: "planning",
  extraction: "extraction",
  chat: "chat",
  research: "research",
};

// --- Types ---

interface CategoryOverridesProps {
  readonly overrides: Record<string, ModelOverride>;
  readonly providers: UserProvider[];
  readonly onChange: (overrides: Record<string, ModelOverride>) => void;
  readonly modelOptions: Record<string, { value: string; label: string }[]>;
  readonly loadingModels?: Record<string, boolean>;
}

// --- Component ---

export function CategoryOverrides({
  overrides,
  providers,
  onChange,
  modelOptions,
  loadingModels,
}: CategoryOverridesProps) {
  const t = useTranslations("studio");

  const activeProviders = providers.filter((p) => p.is_active);

  const toggleOverride = (category: IntentCategory) => {
    const updated = { ...overrides };
    if (updated[category]) {
      delete updated[category];
    } else {
      const firstProvider = activeProviders[0];
      if (firstProvider) {
        updated[category] = { provider_id: firstProvider.id, model_id: "" };
      }
    }
    onChange(updated);
  };

  const updateOverride = (
    category: IntentCategory,
    field: "provider_id" | "model_id",
    value: string,
  ) => {
    const updated = { ...overrides };
    const existing = updated[category];
    if (field === "provider_id") {
      updated[category] = { provider_id: value, model_id: "" };
    } else if (existing) {
      updated[category] = { ...existing, model_id: value };
    }
    onChange(updated);
  };

  return (
    <div className="ml-15 space-y-3">
      {CATEGORY_VALUES.map((catValue) => {
        const override = overrides[catValue];
        const isActive = !!override;
        const modelsForProvider = override ? (modelOptions[override.provider_id] ?? []) : [];
        const isLoading = override ? loadingModels?.[override.provider_id] : false;
        const catLabel = t(`settings.ai.categories.${CATEGORY_LABEL_KEYS[catValue]}`);

        return (
          <div
            key={catValue}
            className={cn(
              "border border-border rounded-md p-4 transition-colors",
              isActive && "border-primary/30 bg-accent/20",
            )}
          >
            <div className="flex items-center justify-between gap-4">
              <span className="text-sm font-medium">{catLabel}</span>
              <button
                type="button"
                onClick={() => toggleOverride(catValue)}
                className={cn(
                  "relative w-11 h-6 rounded-full transition-colors duration-200 shrink-0",
                  isActive ? "bg-primary" : "bg-muted-foreground/30",
                )}
                role="switch"
                aria-checked={isActive}
                aria-label={`${isActive ? t("settings.ai.categoryOverrides.disable") : t("settings.ai.categoryOverrides.enable")} ${catLabel}`}
              >
                <span
                  className={cn(
                    "absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow-sm transition-transform duration-200",
                    isActive ? "translate-x-5" : "translate-x-0",
                  )}
                />
              </button>
            </div>

            {isActive && override && (
              <div className="mt-3 flex gap-3">
                <div className="flex-1">
                  <select
                    value={override.provider_id}
                    onChange={(e) => updateOverride(catValue, "provider_id", e.target.value)}
                    className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
                    aria-label={t("settings.ai.categoryOverrides.selectProvider")}
                  >
                    <option value="">{t("settings.ai.categoryOverrides.selectProvider")}</option>
                    {activeProviders.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.provider_name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex-1">
                  {isLoading ? (
                    <div className="flex items-center gap-2 py-2">
                      <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
                      <span className="text-sm text-muted-foreground">
                        {t("settings.ai.categoryOverrides.loading")}
                      </span>
                    </div>
                  ) : modelsForProvider.length > 0 ? (
                    <select
                      value={override.model_id}
                      onChange={(e) => updateOverride(catValue, "model_id", e.target.value)}
                      className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
                      aria-label={t("settings.ai.categoryOverrides.selectModel")}
                    >
                      <option value="">{t("settings.ai.categoryOverrides.selectModel")}</option>
                      {modelsForProvider.map((m) => (
                        <option key={m.value} value={m.value}>
                          {m.label}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      value={override.model_id}
                      onChange={(e) => updateOverride(catValue, "model_id", e.target.value)}
                      placeholder={t("settings.ai.categoryOverrides.enterModelId")}
                      className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
                    />
                  )}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
