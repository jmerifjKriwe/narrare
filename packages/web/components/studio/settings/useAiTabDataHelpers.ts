import type { ContextTier, UserAiSettings } from "@/types";

export function buildTokenLimitsQuery(aiSettings: UserAiSettings | undefined) {
  return {
    provider: aiSettings?.default_provider_id ?? undefined,
    modelId: aiSettings?.default_model || undefined,
    intent: aiSettings?.default_model ? "write" : undefined,
  };
}

export function normalizeTierPercentages(
  tierPercentages: Record<ContextTier, number>,
): Partial<Record<ContextTier, number>> {
  const normalized: Partial<Record<ContextTier, number>> = {};
  for (const [key, val] of Object.entries(tierPercentages)) {
    normalized[key as ContextTier] = val / 100;
  }
  return normalized;
}
