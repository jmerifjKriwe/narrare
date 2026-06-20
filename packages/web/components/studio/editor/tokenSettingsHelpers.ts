import type { TokenLimitProfile, TokenLimitsResponse } from "@/types";

/**
 * Label keys for the editor panel's compact profile selector.
 *
 * Uses the `tokenSettings.*` namespace (shorter labels than the settings
 * page's `settings.ai.tokenProfile*`). A `Record<TokenLimitProfile, string>`
 * enforces at compile time that every profile has a label — adding a new
 * profile to the type without adding it here is a type error.
 */
export const EDITOR_PROFILE_LABELS: Readonly<Record<TokenLimitProfile, string>> = {
  quick: "tokenSettings.profileQuick",
  balanced: "tokenSettings.profileBalanced",
  long_texts: "tokenSettings.profileLong",
  comprehensive: "tokenSettings.profileComprehensive",
  custom: "tokenSettings.profileCustom",
};

export function getCustomMax(settings: TokenLimitsResponse): number {
  const absoluteMax = settings.metadata.absolute_max;
  const calibration = settings.calibration;
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

export function clampOutputLimit(value: number, max: number): number {
  if (!Number.isFinite(value)) return 1;
  return Math.min(Math.max(Math.round(value), 1), max);
}
