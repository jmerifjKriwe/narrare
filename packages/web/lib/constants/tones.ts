/**
 * Bundled story tone options.
 *
 * Each entry carries a backend `value` and an i18n key (`label`) that resolves
 * via the `studio` translation namespace: `t("tones.balanced")`.
 *
 * Custom tones are fetched at runtime via the `/settings/user/tones` API and
 * merged into tone selectors alongside these bundled defaults.
 */
export const BUNDLED_TONES = [
  { value: "balanced", label: "tones.balanced" },
  { value: "dramatic", label: "tones.dramatic" },
  { value: "humorous", label: "tones.humorous" },
  { value: "suspenseful", label: "tones.suspenseful" },
  { value: "contemplative", label: "tones.contemplative" },
  { value: "romantic", label: "tones.romantic" },
  { value: "dark", label: "tones.dark" },
  { value: "adventurous", label: "tones.adventurous" },
  { value: "quiet", label: "tones.quiet" },
] as const;

export type BundledToneValue = (typeof BUNDLED_TONES)[number]["value"];
