"use client";

/**
 * TokenSettings — compact token limit controls for the Generation Panel.
 *
 * Allows users to adjust output limits and token profiles via slider + select.
 * Uses optimistic updates with debouncing to avoid hammering the API on
 * every slider tick. The slider only commits on mouseUp/blur.
 *
 * API: tokenLimitsApi.getResolved() → TokenLimitsResponse
 *      tokenLimitsApi.updateUser(data) → 204/no-body persistence
 */

import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { tokenLimitsApi } from "@/lib/api/client";
import type { TokenLimitProfile, TokenLimitsResponse } from "@/types";
import { TOKEN_PROFILE_VALUES } from "../settings/aiTabConstants";
import { clampOutputLimit, EDITOR_PROFILE_LABELS, getCustomMax } from "./tokenSettingsHelpers";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TokenSettingsProps {
  /** Optional callback when output limit changes. */
  onOutputLimitChange?: (limit: number) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TokenSettings({ onOutputLimitChange }: TokenSettingsProps) {
  const t = useTranslations("studio");
  const [settings, setSettings] = useState<TokenLimitsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  // Local optimistic value for slider responsiveness
  const [localOutputLimit, setLocalOutputLimit] = useState<number>(4000);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Fetch current settings on mount
  useEffect(() => {
    tokenLimitsApi
      .getResolved()
      .then((res) => {
        setSettings(res);
        setLocalOutputLimit(res.output_limit);
      })
      .finally(() => setLoading(false));
  }, []);

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------

  const refreshResolvedSettings = () => {
    return tokenLimitsApi.getResolved().then((res) => {
      setSettings(res);
      setLocalOutputLimit(res.output_limit);
      return res;
    });
  };

  const handleProfileChange = (newProfile: string) => {
    const profile = newProfile as TokenLimitProfile;
    tokenLimitsApi
      .updateUser({ token_profile: profile })
      .then(refreshResolvedSettings)
      .catch(() => {
        void refreshResolvedSettings();
      });
  };

  const commitOutputLimit = (val: number) => {
    // Cancel any pending debounce
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }

    const max = settings ? getCustomMax(settings) : 131072;
    const nextValue = clampOutputLimit(val, max);

    tokenLimitsApi
      .updateUser({ token_profile: "custom", output_limit: nextValue })
      .then(refreshResolvedSettings)
      .then(() => {
        onOutputLimitChange?.(nextValue);
      })
      .catch(() => {
        // Revert to server state on failure
        void refreshResolvedSettings();
      });
  };

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = Number(e.target.value);
    // Optimistic update for slider responsiveness
    setLocalOutputLimit(val);
    // Debounce API call
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }
    debounceRef.current = setTimeout(() => commitOutputLimit(val), 500);
  };

  const handleSliderCommit = () => {
    // Commit immediately on mouseUp/blur
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }
    commitOutputLimit(localOutputLimit);
  };

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  if (loading || !settings) {
    return null;
  }

  const recommendedMax = settings.metadata.ux_recommended_max;
  const customMax = getCustomMax(settings);
  const recommendedSliderValue = clampOutputLimit(localOutputLimit, recommendedMax);

  return (
    <div className="flex flex-col gap-3">
      {/* Section label */}
      <div className="text-[0.75rem] font-semibold uppercase tracking-wider text-muted-foreground">
        {t("tokenSettings.title")}
      </div>

      {/* Profile selector */}
      <div className="flex flex-col gap-1.5">
        <label htmlFor="token-profile" className="text-xs text-muted-foreground">
          {t("tokenSettings.profile")}
        </label>
        <select
          id="token-profile"
          value={settings.token_profile}
          onChange={(e) => handleProfileChange(e.target.value)}
          className="w-full px-3 py-2 border border-border rounded-lg bg-background text-foreground text-sm outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
        >
          {TOKEN_PROFILE_VALUES.map((value) => (
            <option key={value} value={value}>
              {t(EDITOR_PROFILE_LABELS[value])}
            </option>
          ))}
        </select>
      </div>

      {/* Output limit slider */}
      <div className="flex flex-col gap-1.5">
        <label htmlFor="output-limit" className="text-xs text-muted-foreground">
          {t("tokenSettings.outputLimit")}: {localOutputLimit}
        </label>
        <div className="text-xs text-muted-foreground">
          {t("tokenSettings.recommendedRange", { max: recommendedMax })}
        </div>
        <input
          id="output-limit"
          type="range"
          min={1}
          max={recommendedMax}
          step={100}
          value={recommendedSliderValue}
          onChange={handleSliderChange}
          onMouseUp={handleSliderCommit}
          onBlur={handleSliderCommit}
          className="w-full accent-primary"
          aria-label={t("tokenSettings.outputLimit")}
        />
        <input
          type="number"
          min={1}
          max={customMax}
          step={1}
          value={localOutputLimit}
          onChange={(e) => setLocalOutputLimit(Number(e.target.value))}
          onBlur={handleSliderCommit}
          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
          aria-label={t("tokenSettings.customOutputLimit")}
        />
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>1</span>
          <span>{t("tokenSettings.max", { max: customMax })}</span>
        </div>
      </div>
    </div>
  );
}
