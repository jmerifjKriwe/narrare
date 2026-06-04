import type { ContextTier, TokenLimitProfile } from "@/types";

export const TOKEN_PROFILES: { value: TokenLimitProfile; labelKey: string }[] = [
  { value: "quick", labelKey: "settings.ai.tokenProfileQuick" },
  { value: "balanced", labelKey: "settings.ai.tokenProfileBalanced" },
  { value: "long_texts", labelKey: "settings.ai.tokenProfileLong" },
  { value: "custom", labelKey: "settings.ai.tokenProfileCustom" },
];

export const DEFAULT_TIER_PERCENTAGES: Record<ContextTier, number> = {
  immediate: 30,
  recent: 20,
  kb_referenced: 25,
  kb_suggested: 15,
  pinned: 10,
};
