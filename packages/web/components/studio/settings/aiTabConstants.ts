import { TOKEN_PROFILE_VALUES } from "@/lib/token-profiles";
import type { ContextTier, TokenLimitProfile } from "@/types";

/**
 * Re-exported so existing imports (`TOKEN_PROFILE_VALUES` from this module,
 * e.g. the editor panel) keep resolving. The canonical definition lives in
 * `lib/token-profiles` and is parity-tested there.
 */
export { TOKEN_PROFILE_VALUES };

/**
 * i18n label keys for the settings page profile selector, keyed by profile
 * value. A `Record<TokenLimitProfile, string>` enforces at compile time that
 * every public profile has a label — adding a profile to the type without a
 * label here is a type error.
 *
 * The catalogue itself comes from the API at runtime; this map only labels it.
 */
export const PROFILE_LABEL_KEYS: Readonly<Record<TokenLimitProfile, string>> = {
  quick: "settings.ai.tokenProfileQuick",
  balanced: "settings.ai.tokenProfileBalanced",
  long_texts: "settings.ai.tokenProfileLong",
  comprehensive: "settings.ai.tokenProfileComprehensive",
  custom: "settings.ai.tokenProfileCustom",
};

/**
 * Compile-time fallback option list (value + label key). Runtime UI prefers
 * the API `metadata.catalogue` payload; this constant is the parity anchor
 * tested in `lib/__tests__/token-profiles.test.ts`.
 *
 * `conservative` is intentionally absent (CR-08 P1 D2).
 */
export const TOKEN_PROFILES: { value: TokenLimitProfile; labelKey: string }[] =
  TOKEN_PROFILE_VALUES.map((value) => ({ value, labelKey: PROFILE_LABEL_KEYS[value] }));

export const DEFAULT_TIER_PERCENTAGES: Record<ContextTier, number> = {
  immediate: 30,
  recent: 20,
  kb_referenced: 25,
  kb_suggested: 15,
  pinned: 10,
};
