/**
 * The relation vocabulary's CRUD helpers (W5 Task 4) — the autocomplete
 * suggestions and the label-to-type resolver the type box rides. D7: the
 * stored type is free text; a suggestion picked by its wording resolves back
 * to the vocabulary key so the graph re-localizes it, any other input rides
 * as itself. The round trip is the label helper's inverse, in every catalog.
 */
import { describe, expect, it } from "vitest";

import { applyLocale } from "@shell/lib/locale";
import { t } from "@shell/lib/i18n";
import { de } from "@shell/lib/test/catalogs";

import { RELATION_TYPES, relationTypeLabel, relationTypeOptions, resolveRelationType } from "./relations";

describe("relationTypeOptions", () => {
  it("offers the whole vocabulary, each key beside its localized wording", () => {
    applyLocale("de");
    const options = relationTypeOptions(t);
    expect(options).toHaveLength(RELATION_TYPES.length);
    expect(options.map((option) => option.key)).toEqual([...RELATION_TYPES]);
    const ally = options.find((option) => option.key === "ally_of");
    expect(ally?.label).toBe(de["knowledge.relation.ally_of"]);
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

describe("resolveRelationType — the stored free-text guard (review fix)", () => {
  it("a label-colliding free-text type round-trips as itself on an untouched save", () => {
    applyLocale("de");
    // The stored type is FREE TEXT that happens to spell the de label of ally_of.
    const colliding = de["knowledge.relation.ally_of"];
    expect(resolveRelationType(t, colliding, colliding)).toBe(colliding);
    expect(resolveRelationType(t, colliding, colliding)).not.toBe("ally_of");
  });

  it("a stored KEY still resolves its label back to the key", () => {
    applyLocale("de");
    const label = de["knowledge.relation.ally_of"];
    expect(resolveRelationType(t, label, "ally_of")).toBe("ally_of");
  });

  it("a fresh create (no stored type) still canonicalizes a picked suggestion", () => {
    applyLocale("de");
    const label = de["knowledge.relation.ally_of"];
    expect(resolveRelationType(t, label)).toBe("ally_of");
  });

  it("an EDITED free-text value resolves normally — the guard is the untouched corner only", () => {
    applyLocale("de");
    const stored = "Neuro-Link";
    // The writer picks a different suggestion: it canonicalizes.
    expect(resolveRelationType(t, de["knowledge.relation.enemy_of"], stored)).toBe("enemy_of");
    // The writer types other free text: it rides as itself.
    expect(resolveRelationType(t, "Direkter Kanal", stored)).toBe("Direkter Kanal");
  });
});
