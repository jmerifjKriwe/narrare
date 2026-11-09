import { afterEach, describe, expect, it, vi } from "vitest";

import { formatDate, formatNumber, formattingLocale } from "./format";
import { applyLocale } from "./locale";

/** A stubbed browser makes the regional choice testable on any machine. */
function browserSpeaks(language: string): void {
  vi.stubGlobal("navigator", { language, languages: [language] });
}

afterEach(() => {
  vi.unstubAllGlobals();
  applyLocale("en");
});

describe("formattingLocale", () => {
  it("keeps the chosen language and takes the browser's region", () => {
    browserSpeaks("de-AT");
    applyLocale("de");

    expect(formattingLocale()).toBe("de-AT");
  });

  it("ignores a browser language the app is not speaking", () => {
    browserSpeaks("en-US");
    applyLocale("de");

    expect(formattingLocale()).toBe("de");
  });

  it("falls back to the active catalog without a browser", () => {
    vi.stubGlobal("navigator", undefined);
    applyLocale("fr");

    expect(formattingLocale()).toBe("fr");
  });
});

describe("formatting", () => {
  it("formats a date in the browser's regional variant", () => {
    browserSpeaks("en-GB");
    applyLocale("en");
    const date = new Date(Date.UTC(2024, 0, 2, 12));

    expect(formatDate(date, { dateStyle: "medium" })).toBe(
      new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(date),
    );
  });

  it("formats a number in the browser's regional variant", () => {
    browserSpeaks("de-AT");
    applyLocale("de");

    expect(formatNumber(1234.5)).toBe(new Intl.NumberFormat("de-AT").format(1234.5));
  });
});
