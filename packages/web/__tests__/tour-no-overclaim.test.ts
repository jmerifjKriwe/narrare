import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

type ConceptualTourStep = {
  title: string;
  description: string;
};

type LocaleBlock = {
  tour: {
    step7: ConceptualTourStep;
    step8: ConceptualTourStep;
    step9: ConceptualTourStep;
  };
};

type Locale = "de" | "en" | "fr";

type ForbiddenPattern = {
  label: string;
  pattern: RegExp;
};

const LOCALES: readonly Locale[] = ["de", "en", "fr"] as const;

const FORBIDDEN_PATTERNS: Record<Locale, readonly ForbiddenPattern[]> = {
  de: [
    {
      label: "immer (absolute AI context claim)",
      pattern:
        /\b(?:narrare|ki)\b.{0,40}\b(?:nutzt|verwendet|liest|berücksichtigt|bezieht|lernt)\b.{0,40}\bimmer\b|\b(?:narrare|ki)\b.{0,40}\bimmer\b.{0,40}\b(?:nutzt|verwendet|liest|berücksichtigt|bezieht|lernt)\b/iu,
    },
    { label: "jede KI-Aktion", pattern: /\bjede\s+ki[- ]aktion\b/iu },
    { label: "vollständige KB", pattern: /\bvollständige\s+kb\b/iu },
    { label: "gesamte KB", pattern: /\bgesamte\s+kb\b/iu },
    { label: "automatisch lernt", pattern: /\bautomatisch\s+lernt\b/iu },
    { label: "merkt sich", pattern: /\bmerkt\s+sich\b/iu },
  ],
  en: [
    { label: "always uses", pattern: /\balways uses\b/iu },
    { label: "every AI action", pattern: /\bevery ai action\b/iu },
    {
      label: "automatically reads your full KB",
      pattern: /\bautomatically reads your full kb\b/iu,
    },
    { label: "reads your entire", pattern: /\breads your entire\b/iu },
    {
      label: "always includes your full KB",
      pattern: /\balways includes your full kb\b/iu,
    },
    { label: "the AI memorizes", pattern: /\bthe ai memorizes\b/iu },
    {
      label: "automatically learns your style",
      pattern: /\bautomatically learns your style\b/iu,
    },
  ],
  fr: [
    {
      label: "toujours (absolute AI context claim)",
      pattern:
        /\b(?:narrare|ia)\b.{0,40}\b(?:utilise|lit|inclut|apprend)\b.{0,40}\btoujours\b|\b(?:narrare|ia)\b.{0,40}\btoujours\b.{0,40}\b(?:utilise|lit|inclut|apprend)\b/iu,
    },
    { label: "chaque action", pattern: /\bchaque\s+action\b/iu },
    { label: "KB complète", pattern: /\bkb\s+complète\b/iu },
    { label: "toute votre KB", pattern: /\btoute\s+votre\s+kb\b/iu },
    { label: "apprend automatiquement", pattern: /\bapprend\s+automatiquement\b/iu },
    { label: "mémorise", pattern: /\bmémorise\b/iu },
  ],
};

const CURRENT_DIR = dirname(fileURLToPath(import.meta.url));

function loadLocale(locale: Locale): LocaleBlock {
  const path = resolve(CURRENT_DIR, "..", "..", "i18n", "messages", locale, "studio.json");
  return JSON.parse(readFileSync(path, "utf-8")) as LocaleBlock;
}

describe("tour conceptual steps — RULE-22 no over-claim", () => {
  const localeBlocks = Object.fromEntries(
    LOCALES.map((locale) => [locale, loadLocale(locale)]),
  ) as Record<Locale, LocaleBlock>;

  it.each(
    LOCALES.flatMap(
      (locale) =>
        [
          [locale, "step7", localeBlocks[locale].tour.step7],
          [locale, "step8", localeBlocks[locale].tour.step8],
          [locale, "step9", localeBlocks[locale].tour.step9],
        ] as const,
    ),
  )("%s %s description contains no forbidden absolute claim", (locale, _name, step) => {
    const haystack = `${step.title} ${step.description}`.toLowerCase();
    const hits = FORBIDDEN_PATTERNS[locale]
      .filter(({ pattern }) => pattern.test(haystack))
      .map(({ label }) => label);

    expect(hits, `forbidden phrases found: ${hits.join(", ")}`).toEqual([]);
  });

  it.each(LOCALES)("%s step7 description mentions the KB concept", (locale) => {
    expect(localeBlocks[locale].tour.step7.description.toLowerCase()).toMatch(
      /knowledge base|\bkb\b/,
    );
  });

  it.each(LOCALES)("%s step8 description mentions storyboard or chapter structure", (locale) => {
    expect(localeBlocks[locale].tour.step8.description.toLowerCase()).toMatch(
      /storyboard|chapter|chapitre|kapitel|outline|narrative|erzählbogen|arc narratif/,
    );
  });

  it.each(LOCALES)("%s step9 description includes a concrete before/after example", (locale) => {
    expect(localeBlocks[locale].tour.step9.description.toLowerCase()).toMatch(
      /avant|après|before|without|nachher|ohne|after|vorher|sans/,
    );
  });
});
