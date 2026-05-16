"use client";

import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { cn } from "@/lib/utils";
import type { IntentCategory, ModelOverride, UserProvider } from "@/types";

// --- Static config ---

const CATEGORY_INTENT_KEYS: Record<IntentCategory, { value: string; labelKey: string }[]> = {
  writing: [
    { value: "WRITE", labelKey: "write" },
    { value: "EXTEND", labelKey: "extend" },
    { value: "REWRITE", labelKey: "rewrite" },
    { value: "CO_AUTHOR", labelKey: "coAuthor" },
  ],
  analysis: [
    { value: "ANALYSE", labelKey: "analyse" },
    { value: "SENTIMENT", labelKey: "sentiment" },
    { value: "CONSISTENCY", labelKey: "consistency" },
    { value: "BETA_READ", labelKey: "betaRead" },
    { value: "VOICE", labelKey: "voice" },
  ],
  kb: [
    { value: "KB_CREATE", labelKey: "kbCreate" },
    { value: "KB_IMPROVE", labelKey: "kbImprove" },
    { value: "KB_EXTRACT", labelKey: "kbExtract" },
  ],
  planning: [
    { value: "PLAN", labelKey: "plan" },
    { value: "SUMMARIZE", labelKey: "summarize" },
  ],
  extraction: [
    { value: "EXTRACT", labelKey: "extract" },
    { value: "SUGGEST", labelKey: "suggest" },
  ],
  chat: [{ value: "CHAT", labelKey: "chat" }],
  research: [{ value: "RESEARCH", labelKey: "research" }],
};

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

interface IntentOverridesProps {
  readonly overrides: Record<string, ModelOverride>;
  readonly providers: UserProvider[];
  readonly onChange: (overrides: Record<string, ModelOverride>) => void;
  readonly modelOptions: Record<string, { value: string; label: string }[]>;
  readonly loadingModels?: Record<string, boolean>;
}

// --- Component ---

export function IntentOverrides({
  overrides,
  providers,
  onChange,
  modelOptions,
  loadingModels,
}: IntentOverridesProps) {
  const t = useTranslations("studio");
  const [expanded, setExpanded] = useState(false);
  const [openCategories, setOpenCategories] = useState<Set<string>>(new Set(["writing"]));

  const activeProviders = providers.filter((p) => p.is_active);

  const toggleCategory = (category: string) => {
    setOpenCategories((prev) => {
      const next = new Set(prev);
      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }
      return next;
    });
  };

  const toggleIntentOverride = (intent: string) => {
    const updated = { ...overrides };
    if (updated[intent]) {
      delete updated[intent];
    } else {
      const firstProvider = activeProviders[0];
      if (firstProvider) {
        updated[intent] = { provider_id: firstProvider.id, model_id: "" };
      }
    }
    onChange(updated);
  };

  const updateIntentOverride = (
    intent: string,
    field: "provider_id" | "model_id",
    value: string,
  ) => {
    const updated = { ...overrides };
    const existing = updated[intent];
    if (field === "provider_id") {
      updated[intent] = { provider_id: value, model_id: "" };
    } else if (existing) {
      updated[intent] = { ...existing, model_id: value };
    }
    onChange(updated);
  };

  if (!expanded) {
    return (
      <div className="ml-15 pt-2">
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          {t("settings.ai.intentOverrides.advanced")}
        </button>
      </div>
    );
  }

  return (
    <div className="ml-15 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">
          {t("settings.ai.intentOverrides.description")}
        </span>
        <button
          type="button"
          onClick={() => setExpanded(false)}
          className="text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          {t("settings.ai.intentOverrides.collapse")}
        </button>
      </div>

      {CATEGORY_VALUES.map((category) => {
        const intents = CATEGORY_INTENT_KEYS[category];
        const isOpen = openCategories.has(category);
        const catLabel = t(`settings.ai.categories.${CATEGORY_LABEL_KEYS[category]}`);

        return (
          <div key={category} className="border border-border rounded-md overflow-hidden">
            <button
              type="button"
              onClick={() => toggleCategory(category)}
              className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-accent/50 transition-colors"
              aria-expanded={isOpen}
            >
              <span className="text-sm font-medium">{catLabel}</span>
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
                  const modelsForProvider = override
                    ? (modelOptions[override.provider_id] ?? [])
                    : [];
                  const isLoading = override ? loadingModels?.[override.provider_id] : false;
                  const intentLabel = t(`settings.ai.intents.${intent.labelKey}`);

                  return (
                    <div key={intent.value} className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">{intentLabel}</span>
                        <button
                          type="button"
                          onClick={() => toggleIntentOverride(intent.value)}
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
                                updateIntentOverride(intent.value, "provider_id", e.target.value)
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
                                  updateIntentOverride(intent.value, "model_id", e.target.value)
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
                                  updateIntentOverride(intent.value, "model_id", e.target.value)
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
      })}
    </div>
  );
}
