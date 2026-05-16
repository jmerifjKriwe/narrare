"use client";

import { useTranslations } from "next-intl";
import { Select } from "@/components/ui/Select";
import { getProviderLabel } from "@/lib/providers";
import { cn } from "@/lib/utils";
import type { IntentCategory, ModelOverride, UserProvider } from "@/types";

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

interface CategoryOverridesProps {
  readonly overrides: Record<string, ModelOverride>;
  readonly providers: UserProvider[];
  readonly onChange: (overrides: Record<string, ModelOverride>) => void;
  readonly modelOptions: Record<string, { value: string; label: string }[]>;
  readonly loadingModels?: Record<string, boolean>;
}

export function CategoryOverrides({
  overrides,
  providers,
  onChange,
  modelOptions,
  loadingModels,
}: CategoryOverridesProps) {
  const t = useTranslations("settings-ai.categoryOverrides");
  const tCategories = useTranslations("settings-ai.categories");

  const activeProviders = providers.filter((p) => p.is_active);
  const providerOptions = activeProviders.map((p) => ({
    value: p.id,
    label: getProviderLabel(p.provider_name),
  }));

  const toggleOverride = (category: IntentCategory) => {
    const updated = { ...overrides };
    if (updated[category]) {
      delete updated[category];
    } else {
      const firstProvider = activeProviders[0];
      if (firstProvider) {
        updated[category] = {
          provider_id: firstProvider.id,
          model_id: "",
        };
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
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h3 className="text-[0.9375rem] font-semibold text-foreground">
          {t("title")}
        </h3>
        <span className="text-[0.75rem] text-muted-foreground">{t("description")}</span>
      </div>

      <div className="flex flex-col gap-3">
        {CATEGORY_VALUES.map((catValue) => {
          const override = overrides[catValue];
          const isActive = !!override;
          const modelsForProvider = override ? (modelOptions[override.provider_id] ?? []) : [];
          const isLoading = override ? loadingModels?.[override.provider_id] : false;
          const catLabel = tCategories(CATEGORY_LABEL_KEYS[catValue]);

          return (
            <div
              key={catValue}
              className={cn(
                "border border-border rounded-xl p-4 transition-all duration-200",
                isActive && "border-primary/30 bg-accent/20",
              )}
            >
              <div className="flex items-center justify-between gap-4">
                 <span className="text-[0.9375rem] font-medium text-foreground min-w-[120px]">
                  {catLabel}
                </span>
                <button
                  type="button"
                  onClick={() => toggleOverride(catValue)}
                  className={cn(
                    "relative w-11 h-6 rounded-full transition-colors duration-200 shrink-0",
                     isActive ? "bg-primary" : "bg-muted-foreground/30",
                  )}
                  role="switch"
                  aria-checked={isActive}
                  aria-label={`${isActive ? t("disable") : t("enable")} ${catLabel}`}
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
                    <Select
                      label={t("selectProvider")}
                      value={override.provider_id}
                      onChange={(e) => updateOverride(catValue, "provider_id", e.target.value)}
                      options={providerOptions}
                      placeholder={t("selectProvider")}
                    />
                  </div>
                  <div className="flex-1">
                    {isLoading ? (
                      <div className="flex flex-col gap-1.5">
                        <span className="text-[0.75rem] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
                          {t("selectModel")}
                        </span>
                        <span className="text-[0.8125rem] text-muted-foreground py-2">
                          {t("loading")}
                        </span>
                      </div>
                    ) : modelsForProvider.length > 0 ? (
                      <Select
                        label={t("selectModel")}
                        value={override.model_id}
                        onChange={(e) => updateOverride(catValue, "model_id", e.target.value)}
                        options={modelsForProvider}
                        placeholder={t("selectModel")}
                      />
                    ) : (
                      <div className="flex flex-col gap-1.5">
                        <label
                          htmlFor={`category-model-${catValue}`}
                           className="text-[0.75rem] font-semibold uppercase tracking-[0.1em] text-muted-foreground"
                        >
                          {t("selectModel")}
                        </label>
                        <input
                          id={`category-model-${catValue}`}
                          type="text"
                          value={override.model_id}
                          onChange={(e) => updateOverride(catValue, "model_id", e.target.value)}
                          placeholder={t("enterModelId")}
                           className="w-full px-4 py-3 border border-border rounded-xl bg-card text-foreground text-[0.9375rem] transition-all duration-300 outline-none placeholder:text-muted-foreground focus:border-ring focus:ring-2 focus:ring-ring/15"
                        />
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
