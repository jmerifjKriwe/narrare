"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import type { IntentCategory, ModelOverride, UserProvider } from "@/types";
import { IntentCategoryPanel } from "./IntentCategoryPanel";

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
          <IntentCategoryPanel
            key={category}
            category={category}
            categoryLabel={catLabel}
            intents={intents}
            isOpen={isOpen}
            overrides={overrides}
            activeProviders={activeProviders}
            modelOptions={modelOptions}
            loadingModels={loadingModels}
            onToggleCategory={toggleCategory}
            onToggleIntent={toggleIntentOverride}
            onUpdateOverride={updateIntentOverride}
          />
        );
      })}
    </div>
  );
}
