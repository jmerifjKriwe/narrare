"use client";

import { useTranslations } from "next-intl";
import { getProviderLabel } from "@/lib/providers";
import { cn } from "@/lib/utils";
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

type SettingSource = "project" | "user" | "default";

const SOURCE_STYLE_KEYS: Record<SettingSource, { bg: string; text: string; labelKey: string }> = {
  project: {
    bg: "bg-blue-100",
    text: "text-blue-700",
    labelKey: "fromProject",
  },
  user: {
    bg: "bg-green-100",
    text: "text-green-700",
    labelKey: "fromUser",
  },
  default: {
    bg: "bg-gray-100",
    text: "text-gray-600",
    labelKey: "default",
  },
};

interface EffectiveCategorySetting {
  model: string | null;
  provider: string | null;
  source: SettingSource;
  tokenLimits?: TokenLimitOverride | null;
}

interface EffectiveSettingsDisplayProps {
  readonly effectiveSettings: Record<string, EffectiveCategorySetting>;
  readonly defaultModel?: string;
  readonly defaultProvider?: string;
}

export function EffectiveSettingsDisplay({
  effectiveSettings,
  defaultModel,
  defaultProvider,
}: EffectiveSettingsDisplayProps) {
  const t = useTranslations("settings-ai.effectiveSettings");
  const tCategories = useTranslations("settings-ai.categories");

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h3 className="text-[0.9375rem] font-semibold text-foreground">
          {t("title")}
        </h3>
        <span className="text-[0.75rem] text-muted-foreground">{t("description")}</span>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-[0.75rem]">
        {Object.entries(SOURCE_STYLE_KEYS).map(([key, style]) => (
          <div key={key} className="flex items-center gap-1.5">
            <span className={cn("inline-block w-2 h-2 rounded-full", style.bg)} />
             <span className="text-muted-foreground">{t(style.labelKey)}</span>
          </div>
        ))}
      </div>

      {/* Default model row */}
      {defaultModel && (
        <div className="border border-border rounded-xl p-4 bg-secondary/30">
          <div className="flex items-center justify-between">
            <div>
               <span className="text-[0.75rem] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
                {t("defaultModel")}
              </span>
               <p className="text-[0.9375rem] text-foreground mt-0.5">
                {defaultModel}
                {defaultProvider && (
                   <span className="text-muted-foreground ml-2">
                    {t("viaProvider", { provider: getProviderLabel(defaultProvider) })}
                  </span>
                )}
              </p>
            </div>
            <span
              className={cn(
                "text-[0.625rem] font-medium px-2 py-0.5 rounded-full uppercase tracking-wider",
                SOURCE_STYLE_KEYS.default.bg,
                SOURCE_STYLE_KEYS.default.text,
              )}
            >
              {t(SOURCE_STYLE_KEYS.default.labelKey)}
            </span>
          </div>
        </div>
      )}

      {/* Per-category settings */}
      <div className="flex flex-col gap-2">
        {CATEGORY_VALUES.map((catValue) => {
          const setting = effectiveSettings[catValue];
          if (!setting) return null;

          const style = SOURCE_STYLE_KEYS[setting.source];

          return (
            <div key={catValue} className="border border-border rounded-xl p-4">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                     <span className="text-[0.875rem] font-medium text-foreground">
                      {tCategories(CATEGORY_LABEL_KEYS[catValue])}
                    </span>
                    <span
                      className={cn(
                        "text-[0.625rem] font-medium px-2 py-0.5 rounded-full uppercase tracking-wider",
                        style.bg,
                        style.text,
                      )}
                    >
                      {t(style.labelKey)}
                    </span>
                  </div>
                  {setting.model ? (
                     <p className="text-[0.8125rem] text-muted-foreground">
                      {setting.model}
                      {setting.provider && (
                         <span className="text-muted-foreground ml-1">
                          {t("viaProvider", { provider: getProviderLabel(setting.provider) })}
                        </span>
                      )}
                    </p>
                  ) : (
                    <p className="text-[0.8125rem] text-muted-foreground">
                      {t("usesDefaultModel")}
                    </p>
                  )}
                  {setting.tokenLimits && (
                    <p className="text-[0.75rem] text-muted-foreground mt-0.5">
                      {t("summary", {
                        maxTokens: String(setting.tokenLimits.max_tokens),
                        temp: String(setting.tokenLimits.temperature),
                      })}
                    </p>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
