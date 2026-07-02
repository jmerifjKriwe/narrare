"use client";

/**
 * StyleVariantPicker — dropdown for selecting a creative direction and
 * triggering style-variant regeneration (CR-AUFG-07-22).
 *
 * Renders a native styled select ("Regenerate as…") listing the 6 approved
 * style variants. Selecting a variant fires {@link StyleVariantPickerProps.onSelect},
 * which the parent wires to `streamStyleVariantRegeneration`.
 *
 * Disabled while a generation is streaming. Uses i18n keys under
 * `styleVariants.*` — no hardcoded strings.
 */

import type { StyleVariant } from "@/lib/api/generation";

/** The finite taxonomy of approved style variants. */
const STYLE_VARIANTS: readonly StyleVariant[] = [
  "leaner",
  "more_lyrical",
  "more_tense",
  "more_intimate",
  "more_dialogue",
  "more_sensory",
] as const;

type StudioTranslator = (key: string) => string;

interface StyleVariantPickerProps {
  /** Currently selected variant, or null when nothing is selected. */
  readonly selectedVariant: StyleVariant | null;
  /** Fired when the user picks a variant from the dropdown. */
  readonly onSelect: (variant: StyleVariant) => void;
  /** When true, the dropdown is disabled (a generation is streaming). */
  readonly isStreaming: boolean;
  /** Translator scoped to the "studio" namespace. */
  readonly t: StudioTranslator;
}

export function StyleVariantPicker({
  selectedVariant,
  onSelect,
  isStreaming,
  t,
}: StyleVariantPickerProps) {
  return (
    <select
      value={selectedVariant ?? ""}
      onChange={(e) => onSelect(e.target.value as StyleVariant)}
      disabled={isStreaming}
      aria-label={t("styleVariants.regenerateAs")}
      data-testid="style-variant-picker"
      className="px-3 py-2 bg-input-background border border-border rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-primary"
    >
      <option value="" disabled>
        {t("styleVariants.regenerateAs")}
      </option>
      {STYLE_VARIANTS.map((variant) => (
        <option key={variant} value={variant} title={t(`styleVariants.${variant}.description`)}>
          {t(`styleVariants.${variant}.label`)}
        </option>
      ))}
    </select>
  );
}
