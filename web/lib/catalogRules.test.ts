import IntlMessageFormat from "intl-messageformat";
import { describe, expect, it } from "vitest";

import { catalogs, locales } from "./generated/catalogs";

// The categories the rule requires. A language whose complete set is exactly
// `one/many/other` — French and Spanish report it — has a `many` with no
// surrounding granularity, so the copy never needs a branch for it. Any larger
// set (Russian's one/few/many/other, English's ordinals) keeps every category.
function requiredCategories(
  locale: string,
  type: Intl.PluralRulesOptions["type"],
): string[] {
  const reported = new Intl.PluralRules(locale, { type }).resolvedOptions().pluralCategories;
  const loneMany = reported.length === 3 && [...reported].sort().join("/") === "many/one/other";
  return loneMany ? reported.filter((category) => category !== "many") : [...reported];
}

interface PluralElement {
  pluralType: Intl.PluralRulesOptions["type"];
  options: Record<string, unknown>;
}

function isPlural(element: object): element is PluralElement {
  return "pluralType" in element;
}

// Walks the parsed AST rather than the raw string: nesting, escaping and
// `selectordinal` are the parser's business, not a regex's.
function missingCategories(locale: string, key: string, message: string): string[] {
  const missing: string[] = [];

  function walk(node: unknown): void {
    if (Array.isArray(node)) {
      for (const part of node) walk(part);
      return;
    }
    if (typeof node !== "object" || node === null) return;

    const element = node as object;
    if (isPlural(element)) {
      for (const category of requiredCategories(locale, element.pluralType)) {
        if (!(category in element.options)) missing.push(`${locale}:${key}:${category}`);
      }
    }
    // Every option's value is an element array; recursing over all values
    // reaches nested plurals without knowing the AST's element shapes.
    for (const value of Object.values(element)) walk(value);
  }

  walk(new IntlMessageFormat(message, locale).getAst());
  return missing;
}

describe("catalog plural rules", () => {
  it("names each category a message skips", () => {
    expect(missingCategories("ru", "count", "{n, plural, one {# роман} other {# романов}}")).toEqual([
      "ru:count:few",
      "ru:count:many",
    ]);
  });

  it("does not require a lone many", () => {
    expect(missingCategories("fr", "count", "{n, plural, one {# roman} other {# romans}}")).toEqual([]);
    expect(missingCategories("es", "count", "{n, plural, one {# libro} other {# libros}}")).toEqual([]);
  });

  it("asks a language without categories for other only", () => {
    expect(missingCategories("ja", "count", "{n, plural, other {# 冊}}")).toEqual([]);
  });

  it("applies the rule to ordinal messages with the ordinal categories", () => {
    expect(missingCategories("en", "rank", "{n, selectordinal, one {st} other {th}}")).toEqual([
      "en:rank:two",
      "en:rank:few",
    ]);
  });

  it("finds a plural nested in another branch", () => {
    const message = "{n, plural, one {{m, plural, one {# book} other {# books}}} other {#}}";
    expect(missingCategories("ru", "shelf", message)).toContain("ru:shelf:few");
  });

  it("lets the parser refuse a message without other", () => {
    expect(() => missingCategories("de", "k", "{n, plural, one {#}}")).toThrow();
  });

  it("knows every language and writes it in canonical case", () => {
    for (const code of locales) {
      expect(Intl.getCanonicalLocales(code)).toEqual([code]);
      const resolved = new Intl.Locale(new Intl.NumberFormat(code).resolvedOptions().locale);
      const wanted = new Intl.Locale(code);
      expect(resolved.language).toBe(wanted.language);
      expect(resolved.script).toBe(wanted.script);
    }
  });

  it("writes every plural message in every catalog with the categories its language requires", () => {
    const missing = locales.flatMap((code) =>
      Object.entries(catalogs[code]).flatMap(([key, message]) => missingCategories(code, key, message)),
    );
    expect(missing).toEqual([]);
  });
});
