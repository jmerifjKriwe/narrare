/**
 * The relation vocabulary's CRUD helpers (W5 Task 4) — the autocomplete
 * suggestions and the label-to-type resolver the type box rides. D7: the
 * stored type is free text; a suggestion picked by its wording resolves back
 * to the vocabulary key so the graph re-localizes it, any other input rides
 * as itself. The round trip is the label helper's inverse, in every catalog.
 */
import { describe, expect, it } from "vitest";

import { catalogs } from "@shell/lib/generated/catalogs";
import { applyLocale } from "@shell/lib/locale";
import { t } from "@shell/lib/i18n";

import { RELATION_TYPES, relationTypeLabel, relationTypeOptions, resolveRelationType } from "./relations";

describe("relationTypeOptions", () => {
  it("offers the whole vocabulary, each key beside its localized wording", () => {
    applyLocale("de");
    const options = relationTypeOptions(t);
    expect(options).toHaveLength(RELATION_TYPES.length);
    expect(options.map((option) => option.key)).toEqual([...RELATION_TYPES]);
    const ally = options.find((option) => option.key === "ally_of");
    expect(ally?.label).toBe(catalogs.de["knowledge.relation.ally_of"]);
  });
});

describe("resolveRelationType — the label helper's inverse", () => {
  it("a picked suggestion's wording resolves back to its key, in every locale", () => {
    for (const locale of ["en", "de", "fr"] as const) {
      applyLocale(locale);
      for (const key of RELATION_TYPES) {
        const label = relationTypeLabel(t, key);
        expect(resolveRelationType(t, label), `${locale}/${key}`).toBe(key);
      }
    }
  });

  it("free text rides as itself, trimmed — D7's open vocabulary", () => {
    applyLocale("de");
    expect(resolveRelationType(t, "  Neuro-Link  ")).toBe("Neuro-Link");
    expect(resolveRelationType(t, "Symbiotische Co-Pilotin")).toBe("Symbiotische Co-Pilotin");
  });

  it("an empty input resolves to the empty string (the box's own required guard)", () => {
    applyLocale("de");
    expect(resolveRelationType(t, "   ")).toBe("");
  });

  it("a stored key round-trips through label then resolver", () => {
    applyLocale("fr");
    const key = "located_in";
    expect(resolveRelationType(t, relationTypeLabel(t, key))).toBe(key);
  });
});
