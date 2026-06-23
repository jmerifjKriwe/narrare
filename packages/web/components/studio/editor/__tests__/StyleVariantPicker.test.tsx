/**
 * StyleVariantPicker tests — dropdown for selecting a creative direction.
 *
 * Tests:
 * 1. Renders all 6 approved variants (+ 1 placeholder)
 * 2. Variant labels come from i18n keys (no hardcoded strings)
 * 3. Variant descriptions are present (title attributes for a11y)
 * 4. onSelect fires when a variant is chosen
 * 5. Disabled during streaming
 * 6. Placeholder "Regenerate as…" visible when nothing selected
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { StyleVariant } from "@/lib/api/generation";
import { StyleVariantPicker } from "../StyleVariantPicker";

/** Mock translator that returns the i18n key verbatim (global next-intl mock). */
const t = (key: string) => key;

const ALL_VARIANTS: StyleVariant[] = [
  "leaner",
  "more_lyrical",
  "more_tense",
  "more_intimate",
  "more_dialogue",
  "more_sensory",
];

function renderPicker(props: Partial<Parameters<typeof StyleVariantPicker>[0]> = {}) {
  const onSelect = vi.fn();
  return {
    onSelect,
    ...render(
      <StyleVariantPicker
        selectedVariant={null}
        onSelect={onSelect}
        isStreaming={false}
        t={t}
        {...props}
      />,
    ),
  };
}

describe("StyleVariantPicker", () => {
  it("renders all 6 variants plus placeholder", () => {
    renderPicker();
    const select = screen.getByRole("combobox");
    // 6 variants + 1 placeholder = 7 options
    expect(select.querySelectorAll("option")).toHaveLength(7);
  });

  it("shows the 'Regenerate as…' placeholder when nothing selected", () => {
    renderPicker();
    expect(screen.getByText("styleVariants.regenerateAs")).toBeInTheDocument();
  });

  it("renders each variant label from i18n keys", () => {
    renderPicker();
    for (const variant of ALL_VARIANTS) {
      expect(screen.getByText(`styleVariants.${variant}.label`)).toBeInTheDocument();
    }
  });

  it("includes variant descriptions as option titles for accessibility", () => {
    const { container } = renderPicker();
    const options = container.querySelectorAll("option");
    // First option is placeholder (no description); remaining 6 have descriptions
    const variantOptions = Array.from(options).slice(1);
    for (const option of variantOptions) {
      expect(option.getAttribute("title")).toMatch(/^styleVariants\./);
    }
  });

  it("calls onSelect when a variant is chosen", () => {
    const { onSelect } = renderPicker();
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "leaner" } });
    expect(onSelect).toHaveBeenCalledWith("leaner");
  });

  it("calls onSelect with the correct variant for each option", () => {
    for (const variant of ALL_VARIANTS) {
      const { onSelect, unmount } = renderPicker();
      fireEvent.change(screen.getByRole("combobox"), { target: { value: variant } });
      expect(onSelect).toHaveBeenCalledWith(variant);
      unmount();
    }
  });

  it("disables the dropdown when streaming", () => {
    renderPicker({ isStreaming: true });
    expect(screen.getByRole("combobox")).toBeDisabled();
  });

  it("reflects the selectedVariant in the dropdown value", () => {
    renderPicker({ selectedVariant: "more_lyrical" as StyleVariant });
    expect(screen.getByRole("combobox")).toHaveValue("more_lyrical");
  });
});
