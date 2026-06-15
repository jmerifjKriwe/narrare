import type { ContextTier, TokenLimitProfile } from "@/types";

export const TOKEN_PROFILES: { value: TokenLimitProfile; labelKey: string }[] = [
  { value: "quick", labelKey: "settings.ai.tokenProfileQuick" },
  { value: "balanced", labelKey: "settings.ai.tokenProfileBalanced" },
  { value: "conservative", labelKey: "settings.ai.tokenProfileConservative" },
  { value: "long_texts", labelKey: "settings.ai.tokenProfileLong" },
  { value: "comprehensive", labelKey: "settings.ai.tokenProfileComprehensive" },
  { value: "custom", labelKey: "settings.ai.tokenProfileCustom" },
];

/**
 * Canonical ordered list of all token profile values.
 *
 * Derived from TOKEN_PROFILES so there is a single source of truth for
 * ordering. Components that need different label keys (e.g. the editor
 * panel uses shorter labels) can map over this list with their own
 * `Record<TokenLimitProfile, string>` lookup.
 */
export const TOKEN_PROFILE_VALUES: readonly TokenLimitProfile[] = TOKEN_PROFILES.map(
  (p) => p.value,
);

export const DEFAULT_TIER_PERCENTAGES: Record<ContextTier, number> = {
  immediate: 30,
  recent: 20,
  kb_referenced: 25,
  kb_suggested: 15,
  pinned: 10,
};
