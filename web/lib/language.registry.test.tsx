// @vitest-environment jsdom
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

/**
 * The switcher draws the registry, not a list of its own: a language the
 * generated module adds appears in the registry's order without a code
 * change. The mock follows the Global Constraints' rule for the test bed —
 * reset the module registry, then import what is tested dynamically.
 */
vi.mock("./generated/catalogs", async (importOriginal) => {
  const real = await importOriginal<typeof import("./generated/catalogs")>();
  return {
    ...real,
    locales: [...real.locales, "pt-BR"],
    localeOrder: [...real.localeOrder, "pt-BR"],
    catalogs: { ...real.catalogs, "pt-BR": { ...real.catalogs.en, "locale.name": "Português (Brasil)" } },
    endonyms: { ...real.endonyms, "pt-BR": "Português (Brasil)" },
  };
});

beforeEach(() => vi.resetModules());
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows a language the registry adds, in the registry's order, without a code change", async () => {
  const { applyLocale } = await import("./locale");
  const { preloadCatalogs } = await import("./test/catalogs");
  const { LanguageSwitcher } = await import("./language");
  // The reset module registry starts empty: the setup file's preload ran on
  // the registry this case discarded. Seed the store before a language is
  // announced — no language is spoken without its catalog.
  preloadCatalogs();
  applyLocale("de");
  render(<LanguageSwitcher variant="welcome" preSetup />);
  const radios = within(screen.getByRole("radiogroup")).getAllByRole("radio");
  expect(radios.map((radio) => radio.textContent)).toEqual(["DE", "EN", "FR", "PT-BR"]);
  expect(radios.map((radio) => radio.getAttribute("aria-label"))).toEqual([
    "Deutsch",
    "English",
    "Français",
    "Português (Brasil)",
  ]);
});
