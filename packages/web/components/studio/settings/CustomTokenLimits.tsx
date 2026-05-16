"use client";

import { useTranslations } from "next-intl";
import type { IntentCategory, TokenLimitOverride } from "@/types";

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

const BALANCED_DEFAULTS: TokenLimitOverride = {
  max_tokens: 2000,
  temperature: 0.7,
};

// --- Types ---

interface CustomTokenLimitsProps {
  readonly overrides: Record<string, TokenLimitOverride>;
  readonly onChange: (overrides: Record<string, TokenLimitOverride>) => void;
}

// --- Component ---

export function CustomTokenLimits({ overrides, onChange }: CustomTokenLimitsProps) {
  const t = useTranslations("studio");

  const getOverride = (category: IntentCategory): TokenLimitOverride => {
    return overrides[category] ?? { ...BALANCED_DEFAULTS };
  };

  const updateOverride = (
    category: IntentCategory,
    field: keyof TokenLimitOverride,
    rawValue: string,
  ) => {
    const numValue = parseFloat(rawValue);
    if (Number.isNaN(numValue)) return;

    if (field === "max_tokens" && numValue < 1) return;
    if (field === "temperature" && (numValue < 0 || numValue > 2)) return;

    const updated = { ...overrides };
    updated[category] = {
      ...getOverride(category),
      [field]: field === "max_tokens" ? Math.round(numValue) : numValue,
    };
    onChange(updated);
  };

  return (
    <div className="ml-15 space-y-3">
      {CATEGORY_VALUES.map((catValue) => {
        const override = getOverride(catValue);
        const isHigh = override.max_tokens > 128000;

        return (
          <div key={catValue} className="border border-border rounded-md p-4">
            <span className="text-sm font-medium block mb-3">
              {t(`settings.ai.categories.${CATEGORY_LABEL_KEYS[catValue]}`)}
            </span>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label
                  htmlFor={`token-max-${catValue}`}
                  className="block text-sm text-muted-foreground mb-1"
                >
                  {t("settings.ai.tokenLimits.maxTokens")}
                </label>
                <input
                  id={`token-max-${catValue}`}
                  type="number"
                  min={1}
                  value={String(override.max_tokens)}
                  onChange={(e) => updateOverride(catValue, "max_tokens", e.target.value)}
                  className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
                />
                {isHigh && (
                  <p className="mt-1 text-xs text-amber-600">
                    {t("settings.ai.tokenLimits.maxTokensWarning", {
                      value: override.max_tokens,
                    })}
                  </p>
                )}
              </div>
              <div>
                <label
                  htmlFor={`token-temp-${catValue}`}
                  className="block text-sm text-muted-foreground mb-1"
                >
                  {t("settings.ai.tokenLimits.temperature")}
                </label>
                <input
                  id={`token-temp-${catValue}`}
                  type="number"
                  min={0}
                  max={2}
                  step={0.1}
                  value={String(override.temperature)}
                  onChange={(e) => updateOverride(catValue, "temperature", e.target.value)}
                  className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
                />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
