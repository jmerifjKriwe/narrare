"use client";

import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import type { TokenLimitProfile } from "@/types";

const PROFILE_VALUES: TokenLimitProfile[] = ["quick", "balanced", "long_texts", "custom"];

interface TokenLimitProfileSelectorProps {
  readonly value: TokenLimitProfile;
  readonly onChange: (profile: TokenLimitProfile) => void;
}

export function TokenLimitProfileSelector({ value, onChange }: TokenLimitProfileSelectorProps) {
  const t = useTranslations("settings-ai.tokenLimitProfile");

  const PROFILE_LABEL_KEYS: Record<TokenLimitProfile, string> = {
    quick: "quick",
    balanced: "balanced",
    long_texts: "longTexts",
    custom: "custom",
  };

  const PROFILE_DESC_KEYS: Record<TokenLimitProfile, string> = {
    quick: "quickDescription",
    balanced: "balancedDescription",
    long_texts: "longTextsDescription",
    custom: "customDescription",
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h3 className="text-[0.9375rem] font-semibold text-[var(--color-text-primary)]">
          {t("title")}
        </h3>
      </div>

      <div className="grid grid-cols-2 gap-3">
        {PROFILE_VALUES.map((profileValue) => {
          const isSelected = value === profileValue;
          const labelKey = PROFILE_LABEL_KEYS[profileValue];
          const descKey = PROFILE_DESC_KEYS[profileValue];

          return (
            <button
              key={profileValue}
              type="button"
              onClick={() => onChange(profileValue)}
              className={cn(
                "text-left border rounded-xl p-4 transition-all duration-200",
                isSelected
                  ? "border-[var(--color-accent)] bg-[var(--color-accent-light)] shadow-sm"
                  : "border-[var(--color-border)] bg-[var(--color-surface)] hover:border-[var(--color-border-strong)] hover:bg-[var(--color-bg-secondary)]",
              )}
              aria-pressed={isSelected}
            >
              <div className="flex items-center gap-2 mb-1">
                <span
                  className={cn(
                    "w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center transition-colors",
                    isSelected ? "border-[var(--color-accent)]" : "border-[var(--color-border)]",
                  )}
                >
                  {isSelected && (
                    <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-accent)]" />
                  )}
                </span>
                <span
                  className={cn(
                    "text-[0.9375rem] font-medium",
                    isSelected ? "text-[var(--color-accent)]" : "text-[var(--color-text-primary)]",
                  )}
                >
                  {t(labelKey)}
                </span>
              </div>
              <p className="text-[0.75rem] text-[var(--color-text-tertiary)] ml-5.5 pl-0.5">
                {t(descKey)}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
