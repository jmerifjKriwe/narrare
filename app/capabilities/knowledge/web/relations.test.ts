import { describe, expect, it } from "vitest";

import { catalogs } from "@shell/lib/generated/catalogs";
import type { MessageKey } from "@shell/lib/i18n";

import { RELATION_TYPES, relationTypeLabel, resolveRelationType } from "./relations";

/**
 * The relation vocabulary's two directions, against the real catalog: a
 * stored type renders in the reader's language (or as itself, when it is
 * no vocabulary entry — free text is a first-class answer, D7), and the
 * box's text resolves back to what the edge stores. `t` reads the English
 * map directly, so the assertions pin the wiring — entry → label, miss →
 * raw — not one wording's spelling.
 */
const t = (key: MessageKey): string => catalogs.en[key];

const items = RELATION_TYPES.map((type) => ({
  id: type,
  text: catalogs.en[`knowledge.relation.${type}` as MessageKey],
}));

describe("relationTypeLabel", () => {
  it("renders a vocabulary entry in the reader's language", () => {
    expect(relationTypeLabel(t, "ally_of")).toBe(t("knowledge.relation.ally_of"));
    expect(relationTypeLabel(t, "enemy_of")).toBe(t("knowledge.relation.enemy_of"));
  });

  it("falls back to the raw string for off-vocabulary text", () => {
    expect(relationTypeLabel(t, "bewohnt")).toBe("bewohnt");
    expect(relationTypeLabel(t, "Kennt sich seit der Kindheit")).toBe(
      "Kennt sich seit der Kindheit",
    );
  });
});

describe("resolveRelationType", () => {
  it("resolves an exact vocabulary label back to its id", () => {
    expect(resolveRelationType(items, t("knowledge.relation.ally_of"))).toBe("ally_of");
    expect(resolveRelationType(items, t("knowledge.relation.owns"))).toBe("owns");
  });

  it("keeps free text as the stored answer, whatever its casing", () => {
    // D7: only the vocabulary's exact label resolves to its id — anything
    // else, a differently cased near-hit included, stores as typed.
    expect(resolveRelationType(items, "bewohnt")).toBe("bewohnt");
    expect(resolveRelationType(items, "Ally OF")).toBe("Ally OF");
  });

  it("trims what the box carries before the lookup", () => {
    const label = t("knowledge.relation.ally_of");
    expect(resolveRelationType(items, `  ${label}  `)).toBe("ally_of");
  });

  it("answers the empty string for a blank box — no type at all", () => {
    // The callers' no-type sentinel: the box carries nothing worth storing.
    expect(resolveRelationType(items, "")).toBe("");
    expect(resolveRelationType(items, "   ")).toBe("");
  });
});
