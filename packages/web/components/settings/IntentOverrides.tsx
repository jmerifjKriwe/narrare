"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { cn } from "@/lib/utils";
import type { IntentCategory, ModelOverride, UserProvider } from "@/types";

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

interface IntentOverridesProps {
  readonly overrides: Record<string, ModelOverride>;
  readonly providers: UserProvider[];
  readonly onChange: (overrides: Record<string, ModelOverride>) => void;
  readonly modelOptions: Record<string, { value: string; label: string }[]>;
  readonly loadingModels?: Record<string, boolean>;
}

export function IntentOverrides({
  overrides,
  providers,
  onChange,
  modelOptions,
  loadingModels,
}: IntentOverridesProps) {
  const t = useTranslations("settings-ai.intentOverrides");
  const tCategories = useTranslations("settings-ai.categories");
  const tIntents = useTranslations("settings-ai.intents");
  const [expanded, setExpanded] = useState(false);
  const [openCategories, setOpenCategories] = useState<Set<string>>(new Set(["writing"]));

  const activeProviders = providers.filter((p) => p.is_active);
  const providerOptions = activeProviders.map((p) => ({
    value: p.id,
    label: p.provider_name,
  }));

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
      <div className="pt-2">
        <Button type="button" variant="ghost" size="sm" onClick={() => setExpanded(true)}>
          {t("advanced")}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 pt-2">
      <div className="flex items-center justify-between">
        <h3 className="text-[0.9375rem] font-semibold text-[var(--color-text-primary)]">
          {t("title")}
        </h3>
        <Button type="button" variant="ghost" size="sm" onClick={() => setExpanded(false)}>
          {t("collapse")}
        </Button>
      </div>

      <p className="text-[0.8125rem] text-[var(--color-text-tertiary)]">{t("description")}</p>

      <div className="flex flex-col gap-2">
        {CATEGORY_VALUES.map((category) => {
          const intents = CATEGORY_INTENT_KEYS[category];
          const isOpen = openCategories.has(category);
          const catLabel = tCategories(CATEGORY_LABEL_KEYS[category]);

          return (
            <div
              key={category}
              className="border border-[var(--color-border)] rounded-xl overflow-hidden"
            >
              <button
                type="button"
                onClick={() => toggleCategory(category)}
                className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-[var(--color-bg-secondary)] transition-colors"
                aria-expanded={isOpen}
              >
                <span className="text-[0.875rem] font-medium text-[var(--color-text-primary)]">
                  {catLabel}
                </span>
                <span
                  className={cn(
                    "text-[var(--color-text-tertiary)] transition-transform duration-200 text-sm",
                    isOpen && "rotate-180",
                  )}
                >
                  ▼
                </span>
              </button>

              {isOpen && (
                <div className="border-t border-[var(--color-border)] px-4 py-3 flex flex-col gap-3 bg-[var(--color-bg-secondary)]/30">
                  {intents.map((intent) => {
                    const override = overrides[intent.value];
                    const isActive = !!override;
                    const modelsForProvider = override
                      ? (modelOptions[override.provider_id] ?? [])
                      : [];
                    const isLoading = override ? loadingModels?.[override.provider_id] : false;
                    const intentLabel = tIntents(intent.labelKey);

                    return (
                      <div key={intent.value} className="flex flex-col gap-2">
                        <div className="flex items-center justify-between">
                          <span className="text-[0.8125rem] text-[var(--color-text-secondary)]">
                            {intentLabel}
                          </span>
                          <button
                            type="button"
                            onClick={() => toggleIntentOverride(intent.value)}
                            className={cn(
                              "relative w-9 h-[18px] rounded-full transition-colors duration-200",
                              isActive ? "bg-[var(--color-accent)]" : "bg-[var(--color-border)]",
                            )}
                            role="switch"
                            aria-checked={isActive}
                            aria-label={`${isActive ? t("disable") : t("enable")} ${intentLabel}`}
                          >
                            <span
                              className={cn(
                                "absolute top-[2px] w-[14px] h-[14px] rounded-full bg-white shadow-sm transition-transform duration-200",
                                isActive ? "translate-x-[18px]" : "translate-x-[2px]",
                              )}
                            />
                          </button>
                        </div>

                        {isActive && override && (
                          <div className="flex gap-3 ml-2">
                            <div className="flex-1">
                              <Select
                                label={t("provider")}
                                value={override.provider_id}
                                onChange={(e) =>
                                  updateIntentOverride(intent.value, "provider_id", e.target.value)
                                }
                                options={providerOptions}
                                placeholder={t("provider")}
                              />
                            </div>
                            <div className="flex-1">
                              {isLoading ? (
                                <span className="text-[0.75rem] text-[var(--color-text-tertiary)]">
                                  {t("loading")}
                                </span>
                              ) : modelsForProvider.length > 0 ? (
                                <Select
                                  label={t("model")}
                                  value={override.model_id}
                                  onChange={(e) =>
                                    updateIntentOverride(intent.value, "model_id", e.target.value)
                                  }
                                  options={modelsForProvider}
                                  placeholder={t("model")}
                                />
                              ) : (
                                <div className="flex flex-col gap-1.5">
                                  <label
                                    htmlFor={`intent-model-${intent.value}`}
                                    className="text-[0.75rem] font-semibold uppercase tracking-[0.1em] text-[var(--color-text-tertiary)]"
                                  >
                                    {t("model")}
                                  </label>
                                  <input
                                    id={`intent-model-${intent.value}`}
                                    type="text"
                                    value={override.model_id}
                                    onChange={(e) =>
                                      updateIntentOverride(intent.value, "model_id", e.target.value)
                                    }
                                    placeholder={t("modelId")}
                                    className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg bg-[var(--color-surface)] text-[var(--color-text-primary)] text-[0.8125rem] transition-all outline-none focus:border-[var(--color-accent)] focus:ring-2 focus:ring-[var(--color-accent)]/15"
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
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
