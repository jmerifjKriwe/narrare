"use client";

import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import type { ModelOverride, UserProvider } from "@/types";

interface IntentCategoryPanelProps {
  readonly category: string;
  readonly categoryLabel: string;
  readonly intents: { value: string; labelKey: string }[];
  readonly isOpen: boolean;
  readonly overrides: Record<string, ModelOverride>;
  readonly activeProviders: UserProvider[];
  readonly modelOptions: Record<string, { value: string; label: string }[]>;
  readonly loadingModels?: Record<string, boolean>;
  readonly onToggleCategory: (category: string) => void;
  readonly onToggleIntent: (intent: string) => void;
  readonly onUpdateOverride: (
    intent: string,
    field: "provider_id" | "model_id",
    value: string,
  ) => void;
}

export function IntentCategoryPanel({
  category,
  categoryLabel,
  intents,
  isOpen,
  overrides,
  activeProviders,
  modelOptions,
  loadingModels,
  onToggleCategory,
  onToggleIntent,
  onUpdateOverride,
}: IntentCategoryPanelProps) {
  const t = useTranslations("studio");

  return (
    <div className="border border-border rounded-md overflow-hidden">
      <button
        type="button"
        onClick={() => onToggleCategory(category)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-accent/50 transition-colors"
        aria-expanded={isOpen}
      >
        <span className="text-sm font-medium">{categoryLabel}</span>
        <span
          className={cn(
            "text-muted-foreground transition-transform duration-200 text-xs",
            isOpen && "rotate-180",
          )}
        >
          ▼
        </span>
      </button>

      {isOpen && (
        <div className="border-t border-border px-4 py-3 space-y-3 bg-background/50">
          {intents.map((intent) => {
            const override = overrides[intent.value];
            const isActive = !!override;
            const modelsForProvider = override ? (modelOptions[override.provider_id] ?? []) : [];
            const isLoading = override ? loadingModels?.[override.provider_id] : false;
            const intentLabel = t(`settings.ai.intents.${intent.labelKey}`);

            return (
              <div key={intent.value} className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">{intentLabel}</span>
                  <button
                    type="button"
                    onClick={() => onToggleIntent(intent.value)}
                    className={cn(
                      "relative w-11 h-6 rounded-full transition-colors duration-200 shrink-0",
                      isActive ? "bg-primary" : "bg-muted-foreground/30",
                    )}
                    role="switch"
                    aria-checked={isActive}
                    aria-label={`${isActive ? t("settings.ai.categoryOverrides.disable") : t("settings.ai.categoryOverrides.enable")} ${intentLabel}`}
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
                  <div className="flex gap-3 ml-2">
                    <div className="flex-1">
                      <select
                        value={override.provider_id}
                        onChange={(e) =>
                          onUpdateOverride(intent.value, "provider_id", e.target.value)
                        }
                        className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
                        aria-label={t("settings.ai.intentOverrides.provider")}
                      >
                        <option value="">{t("settings.ai.intentOverrides.provider")}</option>
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
                            {t("settings.ai.intentOverrides.loading")}
                          </span>
                        </div>
                      ) : modelsForProvider.length > 0 ? (
                        <select
                          value={override.model_id}
                          onChange={(e) =>
                            onUpdateOverride(intent.value, "model_id", e.target.value)
                          }
                          className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
                          aria-label={t("settings.ai.intentOverrides.model")}
                        >
                          <option value="">{t("settings.ai.intentOverrides.model")}</option>
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
                          onChange={(e) =>
                            onUpdateOverride(intent.value, "model_id", e.target.value)
                          }
                          placeholder={t("settings.ai.intentOverrides.modelId")}
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
      )}
    </div>
  );
}
