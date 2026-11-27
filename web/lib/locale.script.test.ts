import { afterEach, beforeEach, expect, it, vi } from "vitest";

/**
 * The script half of the resolution: a registry that carries `zh-Hans` and
 * whose tags name a longer script-and-region form. The mock follows the
 * Global Constraints' rule for the test bed — reset the module registry,
 * then import what is tested dynamically.
 */
vi.mock("./generated/catalogs", async (importOriginal) => {
  const real = await importOriginal<typeof import("./generated/catalogs")>();
  return {
    ...real,
    locales: ["en", "zh-Hans"],
    localeOrder: ["zh-Hans", "en"],
    catalogs: { en: real.catalogs.en, "zh-Hans": { ...real.catalogs.en, "locale.name": "中文（简体）" } },
  };
});

beforeEach(() => vi.resetModules());
afterEach(() => vi.unstubAllGlobals());

it("matches a longer tag onto the same language and script", async () => {
  const { matchLocale, resolveLocale } = await import("./locale");
  expect(matchLocale("zh-Hans-CN")).toBe("zh-Hans");
  expect(resolveLocale("zh-Hans-CN")).toEqual({ catalog: "zh-Hans", formatLocale: "zh-Hans-CN" });
});

it("matches the exact code", async () => {
  const { matchLocale } = await import("./locale");
  expect(matchLocale("zh-Hans")).toBe("zh-Hans");
});

it("does not match a script the registry does not carry", async () => {
  const { matchLocale, resolveLocale } = await import("./locale");
  expect(matchLocale("zh-Hant")).toBeNull();
  expect(resolveLocale("zh-Hant")).toEqual({ catalog: "en", formatLocale: "en" });
});
