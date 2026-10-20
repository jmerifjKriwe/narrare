import { type AIProvider, PROVIDER_IDS, PROVIDER_LABEL_KEYS } from "@/lib/providers.generated";

export type { AIProvider };
export { PROVIDER_IDS, PROVIDER_LABEL_KEYS };

/** Shared provider list with i18n label keys — derived from the generated catalog. */
export const PROVIDERS: { value: AIProvider; labelKey: string }[] = PROVIDER_IDS.map((value) => ({
  value,
  labelKey: PROVIDER_LABEL_KEYS[value],
}));

/** Resolve a provider's display label through the translator; raw value if unknown. */
export function getProviderLabel(value: AIProvider | string, t: (key: string) => string): string {
  const entry = PROVIDERS.find((p) => p.value === value);
  return entry ? t(entry.labelKey) : value;
}
