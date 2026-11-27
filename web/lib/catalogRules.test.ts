import IntlMessageFormat from "intl-messageformat";
import { describe, expect, it } from "vitest";

import { locales } from "./generated/catalogs";
import { merged } from "./test/catalogs";

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

interface Walked {
  missing: string[];
  plurals: number;
}

// Walks the parsed AST rather than the raw string: nesting, escaping and
// `selectordinal` are the parser's business, not a regex's. The plural count
// lets a catalog sweep prove it walked something, so a table shrunken to no
// languages cannot pass as clean.
function walkMessage(locale: string, key: string, message: string): Walked {
  const missing: string[] = [];
  let plurals = 0;

  function walk(node: unknown): void {
    if (Array.isArray(node)) {
      for (const part of node) walk(part);
      return;
    }
    if (typeof node !== "object" || node === null) return;

    const element = node as object;
    if (isPlural(element)) {
      plurals += 1;
      for (const category of requiredCategories(locale, element.pluralType)) {
        if (!(category in element.options)) missing.push(`${locale}:${key}:${category}`);
      }
    }
    // Every option's value is an element array; recursing over all values
    // reaches nested plurals without knowing the AST's element shapes.
    for (const value of Object.values(element)) walk(value);
  }

  walk(new IntlMessageFormat(message, locale).getAst());
  // The engine's category order differs between Node majors — the English
  // ordinals are not listed in a stable order. The rule names a set, not an
  // order, so the report is sorted and the fixtures state sorted arrays.
  return { missing: missing.sort(), plurals };
}

function missingCategories(locale: string, key: string, message: string): string[] {
  return walkMessage(locale, key, message).missing;
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
      "en:rank:few",
      "en:rank:two",
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
    const visited = new Set<string>();
    const missing = locales.flatMap((code) =>
      Object.entries(merged[code]).flatMap(([key, message]) => {
        const walked = walkMessage(code, key, message);
        if (walked.plurals > 0) visited.add(code);
        return walked.missing;
      }),
    );
    expect(missing).toEqual([]);
    // What the walk covered: every language carried at least one plural
    // message, so the clean report above is a real sweep, not an empty one.
    expect([...visited].sort()).toEqual([...locales].sort());
  });
});
