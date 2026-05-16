"use client";

import { useTranslations } from "next-intl";
import { Input } from "@/components/ui/Input";
import type { IntentCategory, TokenLimitOverride } from "@/types";

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

interface CustomTokenLimitsProps {
  readonly overrides: Record<string, TokenLimitOverride>;
  readonly onChange: (overrides: Record<string, TokenLimitOverride>) => void;
}

export function CustomTokenLimits({ overrides, onChange }: CustomTokenLimitsProps) {
  const t = useTranslations("settings-ai.customTokenLimits");
  const tCategories = useTranslations("settings-ai.categories");

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

  const getWarning = (category: IntentCategory): string | null => {
    const override = getOverride(category);
    const COMMON_LIMIT = 128000;
    if (override.max_tokens > COMMON_LIMIT) {
      return t("maxTokensWarning", { value: override.max_tokens });
    }
    return null;
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
          const override = getOverride(catValue);
          const warning = getWarning(catValue);

          return (
            <div key={catValue} className="border border-border rounded-xl p-4">
              <span className="text-[0.875rem] font-medium text-foreground block mb-3">
                {tCategories(CATEGORY_LABEL_KEYS[catValue])}
              </span>
              <div className="grid grid-cols-2 gap-4">
                <Input
                  label={t("maxTokens")}
                  type="number"
                  min={1}
                  value={String(override.max_tokens)}
                  onChange={(e) => updateOverride(catValue, "max_tokens", e.target.value)}
                  error={warning ?? undefined}
                />
                <Input
                  label={t("temperature")}
                  type="number"
                  min={0}
                  max={2}
                  step={0.1}
                  value={String(override.temperature)}
                  onChange={(e) => updateOverride(catValue, "temperature", e.target.value)}
                />
              </div>
              {warning && (
                <p className="mt-2 text-[0.75rem] text-amber-600 flex items-center gap-1">
                  <span aria-hidden="true">⚠</span> {warning}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
