"use client";

/**
 * TokenSettings — compact token limit controls for the Generation Panel.
 *
 * Allows users to adjust output limits and token profiles via slider + select.
 * Uses optimistic updates with debouncing to avoid hammering the API on
 * every slider tick. The slider only commits on mouseUp/blur.
 *
 * API: tokenLimitsApi.getResolved() → TokenLimitsResponse
 *      tokenLimitsApi.updateUser(data) → persist changes
 */

import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { tokenLimitsApi } from "@/lib/api/client";
import type { TokenLimitProfile, TokenLimitsResponse } from "@/types";
import { TOKEN_PROFILE_VALUES } from "../settings/aiTabConstants";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TokenSettingsProps {
  /** Optional callback when output limit changes. */
  onOutputLimitChange?: (limit: number) => void;
}

/**
 * Label keys for the editor panel's compact profile selector.
 *
 * Uses the `tokenSettings.*` namespace (shorter labels than the settings
 * page's `settings.ai.tokenProfile*`). A `Record<TokenLimitProfile, string>`
 * enforces at compile time that every profile has a label — adding a new
 * profile to the type without adding it here is a type error.
 */
const EDITOR_PROFILE_LABELS: Record<TokenLimitProfile, string> = {
  quick: "tokenSettings.profileQuick",
  balanced: "tokenSettings.profileBalanced",
  conservative: "tokenSettings.profileConservative",
  long_texts: "tokenSettings.profileLong",
  comprehensive: "tokenSettings.profileComprehensive",
  custom: "tokenSettings.profileCustom",
};

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

  const handleProfileChange = (newProfile: string) => {
    const profile = newProfile as TokenLimitProfile;
    tokenLimitsApi
      .updateUser({ token_profile: profile })
      .then((res) => {
        setSettings(res);
        setLocalOutputLimit(res.output_limit);
      })
      .catch(() => {
        // Silently fail — next fetch will correct state
      });
  };

  const commitOutputLimit = (val: number) => {
    // Cancel any pending debounce
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }

    tokenLimitsApi
      .updateUser({ output_limit: val })
      .then((res) => {
        setSettings(res);
        setLocalOutputLimit(res.output_limit);
        onOutputLimitChange?.(val);
      })
      .catch(() => {
        // Revert to server state on failure
        tokenLimitsApi.getResolved().then((res) => {
          setSettings(res);
          setLocalOutputLimit(res.output_limit);
        });
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
        <input
          id="output-limit"
          type="range"
          min={500}
          max={16000}
          step={500}
          value={localOutputLimit}
          onChange={handleSliderChange}
          onMouseUp={handleSliderCommit}
          onBlur={handleSliderCommit}
          className="w-full accent-primary"
          aria-label={t("tokenSettings.outputLimit")}
        />
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>500</span>
          <span>{t("tokenSettings.max")}</span>
        </div>
      </div>
    </div>
  );
}
