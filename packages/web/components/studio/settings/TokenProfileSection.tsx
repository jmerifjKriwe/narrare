"use client";

import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";
import type {
  CalibrationMetadata,
  SuitabilityMetadata,
  TokenLimitProfile,
  TokenLimitsCatalog,
} from "@/types";
import { PROFILE_LABEL_KEYS, TOKEN_PROFILES } from "./aiTabConstants";
import { TokenMetadataWarnings } from "./TokenMetadataWarnings";

interface TokenProfileSectionProps {
  readonly currentProfile: TokenLimitProfile;
  readonly outputLimit: number;
  readonly metadata: TokenLimitsCatalog | null;
  readonly calibration: CalibrationMetadata | null;
  readonly suitability: SuitabilityMetadata | null;
  readonly onProfileChange: (profile: TokenLimitProfile) => void;
  readonly onCustomOutputLimitChange: (outputLimit: number) => void;
}

function getEffectiveCustomMax(
  metadata: TokenLimitsCatalog | null,
  calibration: CalibrationMetadata | null,
): number {
  const absoluteMax = metadata?.absolute_max ?? 131072;
  if (
    calibration &&
    (calibration.status === "known_fresh" || calibration.status === "known_stale") &&
    typeof calibration.provider_max_output_tokens === "number" &&
    calibration.provider_max_output_tokens > 0
  ) {
    return Math.min(absoluteMax, calibration.provider_max_output_tokens);
  }
  return absoluteMax;
}

function clampOutputLimit(value: number, max: number): number {
  if (!Number.isFinite(value)) return 1;
  return Math.min(Math.max(Math.round(value), 1), max);
}

export function TokenProfileSection({
  currentProfile,
  outputLimit,
  metadata,
  calibration,
  suitability,
  onProfileChange,
  onCustomOutputLimitChange,
}: TokenProfileSectionProps) {
  const t = useTranslations("studio");
  const [selectedProfile, setSelectedProfile] = useState<TokenLimitProfile>(currentProfile);
  const [customLimit, setCustomLimit] = useState(String(outputLimit));

  useEffect(() => {
    setSelectedProfile(currentProfile);
  }, [currentProfile]);

  useEffect(() => {
    setCustomLimit(String(outputLimit));
  }, [outputLimit]);

  const profileOptions = useMemo(() => {
    const catalogue = metadata?.catalogue;
    if (catalogue && catalogue.length > 0) {
      return catalogue.map((preset) => ({
        value: preset.value,
        labelKey: PROFILE_LABEL_KEYS[preset.value],
      }));
    }
    return TOKEN_PROFILES;
  }, [metadata?.catalogue]);

  const recommendedMax = metadata?.ux_recommended_max ?? 16000;
  const customMax = getEffectiveCustomMax(metadata, calibration);
  const numericCustomLimit = Number(customLimit);
  const recommendedSliderValue = clampOutputLimit(
    Number.isFinite(numericCustomLimit) ? numericCustomLimit : outputLimit,
    recommendedMax,
  );

  function handleProfileChange(value: string) {
    const nextProfile = value as TokenLimitProfile;
    setSelectedProfile(nextProfile);
    onProfileChange(nextProfile);
  }

  function commitCustomLimit() {
    const nextLimit = clampOutputLimit(Number(customLimit), customMax);
    setCustomLimit(String(nextLimit));
    onCustomOutputLimitChange(nextLimit);
  }

  return (
    <div className="bg-card border border-border rounded-lg p-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
          <span className="text-lg">{"\u26A1"}</span>
        </div>
        <div>
          <h3 className="font-medium">{t("settings.ai.tokenProfile")}</h3>
        </div>
      </div>
      <div className="ml-15 space-y-4">
        <select
          value={selectedProfile}
          onChange={(event) => handleProfileChange(event.target.value)}
          className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
        >
          {profileOptions.map(({ value, labelKey }) => (
            <option key={value} value={value}>
              {t(labelKey)}
            </option>
          ))}
        </select>

        {selectedProfile === "custom" && (
          <div className="space-y-3 rounded-md border border-border bg-muted/30 p-4">
            <p className="text-sm font-medium">
              {t("settings.ai.tokenLimits.recommendedRangeLabel")}
            </p>
            <input
              type="range"
              min={1}
              max={recommendedMax}
              step={100}
              value={recommendedSliderValue}
              onChange={(event) => setCustomLimit(event.target.value)}
              onBlur={commitCustomLimit}
              className="w-full accent-foreground"
              aria-label={t("settings.ai.tokenLimits.recommendedRangeLabel")}
            />
            <label className="block space-y-1 text-sm">
              <span className="font-medium">
                {t("settings.ai.tokenLimits.customOutputLimitLabel")}
              </span>
              <input
                type="number"
                min={1}
                max={customMax}
                step={1}
                value={customLimit}
                onChange={(event) => setCustomLimit(event.target.value)}
                onBlur={commitCustomLimit}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              />
            </label>
            <p className="text-xs text-muted-foreground">
              {t("settings.ai.tokenLimits.customOutputLimitHint", {
                recommendedMax,
                max: customMax,
              })}
            </p>
          </div>
        )}

        <TokenMetadataWarnings calibration={calibration} suitability={suitability} />
      </div>
    </div>
  );
}
