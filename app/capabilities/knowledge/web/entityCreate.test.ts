/**
 * The create dialog's pure seam: resolving a typed relation target against
 * the novel's roster, spotting a name that already exists, and turning the
 * form into the POST body. Rows the novel cannot resolve to exactly one
 * entity are left out of the body — the dialog tells the writer so, and a
 * guessed edge would be worse than none.
 */
import { describe, expect, it } from "vitest";

import type { Entity, Proposal } from "@shell/lib/api/client";

import {
  MAX_RELATIONS,
  REFUSAL_CODES,
  RELATION_ROW_CODES,
  buildEntityCreateBody,
  createFormState,
  duplicateRelationRows,
  entityPrefillFromProposal,
  findDuplicateName,
  keptRelationRows,
  refusalCatalogKey,
  refusalNamesRelationRow,
  relationRowOutcome,
  resolveRelationTarget,
  visibleRowForSentIndex,
  type EntityCreateForm,
} from "./entityCreate";

const NOVEL_ID = "11111111-1111-1111-1111-111111111111";

function entityRow(overrides: Partial<Entity> & { id: string; name: string }): Entity {
  return {
    novel_id: NOVEL_ID,
    type: "character",
    aliases: [],
    tags: [],
    content: "",
    created_at: "2026-11-18T10:00:00Z",
    updated_at: "2026-11-18T10:00:00Z",
    ...overrides,
  };
}

const MAYA = entityRow({ id: "e1", name: "Dr. Maya Chen", aliases: ["May"] });
const ARIA = entityRow({ id: "e2", name: "ARIA", aliases: ["May"] });
const STATION = entityRow({ id: "e3", name: "Forschungsstation 7", type: "location" });
const ENTITIES = [MAYA, ARIA, STATION];

function form(overrides: Partial<EntityCreateForm> = {}): EntityCreateForm {
  return {
    novelId: NOVEL_ID,
    name: "Nevada-Trümmerfeld",
    type: "location",
    aliases: ["Nevada"],
    tags: ["Ruine"],
    content: "Ein Feld aus Trümmern.",
    relations: [],
    entities: ENTITIES,
    ...overrides,
  };
}

describe("resolveRelationTarget", () => {
  it("resolves a name, trimmed and case-insensitive", () => {
    expect(resolveRelationTarget("  dr. maya chen ", ENTITIES)).toEqual({
      kind: "one",
      entity: MAYA,
    });
  });

  it("resolves an alias", () => {
    // Both rows carry "May" as an alias — one match must be unique, so pin
    // the alias on a row no other row shares.
    const titled = entityRow({ id: "e4", name: "Kavic", aliases: ["Der Alte"] });
    expect(resolveRelationTarget("der alte", [...ENTITIES, titled])).toEqual({
      kind: "one",
      entity: titled,
    });
  });

  it("two entities sharing an alias give many", () => {
    const resolution = resolveRelationTarget("MAY", ENTITIES);
    expect(resolution.kind).toBe("many");
    if (resolution.kind !== "many") throw new Error("expected many");
    expect(new Set(resolution.entities.map((row) => row.id))).toEqual(new Set(["e1", "e2"]));
  });

  it("no match gives none", () => {
    expect(resolveRelationTarget("Nebel", ENTITIES)).toEqual({ kind: "none" });
    expect(resolveRelationTarget("   ", ENTITIES)).toEqual({ kind: "none" });
  });
});

describe("findDuplicateName", () => {
  it("ignores case and surrounding space", () => {
    expect(findDuplicateName("  dr. maya chen  ", ENTITIES)).toBe(MAYA);
    expect(findDuplicateName("Nebel", ENTITIES)).toBeNull();
    expect(findDuplicateName("   ", ENTITIES)).toBeNull();
  });
});

describe("buildEntityCreateBody", () => {
  it("leaves unresolved rows out", () => {
    const body = buildEntityCreateBody(
      form({
        relations: [
          { target: "Forschungsstation 7", relationType: "Liegt in", note: "  nördlich  " },
          { target: "Nebel", relationType: "kennt", note: "" },
          { target: "May", relationType: "kennt", note: "" },
        ],
      }),
    );
    expect(body.novel_id).toBe(NOVEL_ID);
    expect(body.name).toBe("Nevada-Trümmerfeld");
    expect(body.relations).toEqual([
      { to_entity_id: "e3", relation_type: "Liegt in", note: "nördlich" },
    ]);
  });

  it("leaves a resolved row without a label out, so the dialog can count it", () => {
    const body = buildEntityCreateBody(
      form({
        relations: [{ target: "Forschungsstation 7", relationType: "   ", note: "" }],
      }),
    );
    expect(body.relations).toEqual([]);
  });
});

describe("keptRelationRows", () => {
  it("names the visible rows the save sends, so a sent index finds its row", () => {
    const rows = [
      { target: "Nebel", relationType: "kennt", note: "" },
      { target: "Forschungsstation 7", relationType: "Liegt in", note: "" },
      { target: "Forschungsstation 7", relationType: "", note: "nördlich" },
      { target: "Dr. Maya Chen", relationType: "kennt", note: "" },
    ];
    const kept = keptRelationRows(rows, ENTITIES);
    expect(kept).toEqual([1, 3]);
    expect(visibleRowForSentIndex(kept, 0)).toBe(1);
    expect(visibleRowForSentIndex(kept, 1)).toBe(3);
    expect(visibleRowForSentIndex(kept, 2)).toBeNull();
  });

  it("mirrors the server's twelve-relation bound", () => {
    expect(MAX_RELATIONS).toBe(12);
  });
});

describe("duplicateRelationRows", () => {
  it("flags both rows whose normalized target and label repeat", () => {
    const rows = [
      { target: "Forschungsstation 7", relationType: "located_in", note: "" },
      { target: "  forschungsstation 7 ", relationType: "located_in", note: "anders" },
      { target: "Dr. Maya Chen", relationType: "located_in", note: "" },
    ];
    expect(duplicateRelationRows(rows, ENTITIES)).toEqual([0, 1]);
  });

  it("ignores a different label, a different target and the note", () => {
    const rows = [
      { target: "Forschungsstation 7", relationType: "located_in", note: "a" },
      { target: "Forschungsstation 7", relationType: "kennt", note: "a" },
      { target: "Dr. Maya Chen", relationType: "located_in", note: "a" },
    ];
    expect(duplicateRelationRows(rows, ENTITIES)).toEqual([]);
  });

  it("flags only rows the save sends", () => {
    const rows = [
      { target: "Forschungsstation 7", relationType: "located_in", note: "" },
      { target: "Nebel", relationType: "located_in", note: "" },
      { target: "Forschungsstation 7", relationType: "located_in", note: "" },
    ];
    expect(duplicateRelationRows(rows, ENTITIES)).toEqual([0, 2]);
  });
});

describe("refusalCatalogKey", () => {
  it("maps every closed code to its catalog sentence key", () => {
    expect(REFUSAL_CODES).toEqual([
      "not-found",
      "entity-invalid",
      "relation-target-invalid",
      "relation-duplicate",
      "relation-limit",
    ]);
    for (const code of REFUSAL_CODES) {
      expect(refusalCatalogKey(code)).toBe(`knowledge.create.refused.${code}`);
    }
  });

  it("leaves the synthetic transport code and unknown codes unmapped", () => {
    expect(refusalCatalogKey("transport")).toBeNull();
    expect(refusalCatalogKey("something-else")).toBeNull();
    expect(refusalCatalogKey(undefined)).toBeNull();
  });
});

describe("refusalNamesRelationRow", () => {
  it("names the three row-carrying codes and nothing else", () => {
    expect([...RELATION_ROW_CODES].sort()).toEqual([
      "relation-duplicate",
      "relation-limit",
      "relation-target-invalid",
    ]);
    for (const code of RELATION_ROW_CODES) {
      expect(refusalNamesRelationRow(code)).toBe(true);
    }
    // `entity-invalid` marks a form field; transport and unknown codes no row.
    expect(refusalNamesRelationRow("entity-invalid")).toBe(false);
    expect(refusalNamesRelationRow("not-found")).toBe(false);
    expect(refusalNamesRelationRow("transport")).toBe(false);
    expect(refusalNamesRelationRow(undefined)).toBe(false);
  });
});

describe("relationRowOutcome", () => {
  it("names what the save will do with a row, so nothing drops silently", () => {
    expect(
      relationRowOutcome(
        { target: "  forschungsstation 7 ", relationType: " Liegt in ", note: "" },
        ENTITIES,
      ),
    ).toBe("kept");
    expect(relationRowOutcome({ target: "Forschungsstation 7", relationType: "", note: "" }, ENTITIES)).toBe(
      "missing-label",
    );
    expect(relationRowOutcome({ target: "Nebel", relationType: "kennt", note: "" }, ENTITIES)).toBe(
      "unresolved-target",
    );
    expect(relationRowOutcome({ target: "   ", relationType: "", note: "" }, ENTITIES)).toBe("empty");
  });

  it("a blank target with a typed label is unresolved, never an untouched add-row", () => {
    // The writer filled the label first and left the target for last: the row
    // must be counted and marked, not silently dropped as empty.
    expect(relationRowOutcome({ target: "   ", relationType: "kennt", note: "" }, ENTITIES)).toBe(
      "unresolved-target",
    );
    const body = buildEntityCreateBody(
      form({ relations: [{ target: "  ", relationType: "kennt", note: "" }] }),
    );
    expect(body.relations).toEqual([]);
  });

  it("a blank target with only a note is unresolved too", () => {
    expect(relationRowOutcome({ target: "", relationType: "", note: "  alter Weg  " }, ENTITIES)).toBe(
      "unresolved-target",
    );
  });
});

function proposed(overrides: Partial<Proposal> = {}): Proposal {
  return {
    name: null,
    name_suggested: false,
    aliases: [],
    tags: [],
    content: "",
    relations: [],
    ...overrides,
  };
}

describe("entityPrefillFromProposal", () => {
  it("the prefill maps the proposal", () => {
    const prefill = entityPrefillFromProposal(
      proposed({
        name: "Resonanz-Transponder LC-89",
        name_suggested: true,
        aliases: ["LC-89", "Transponder"],
        tags: ["Technologie", "Relikt"],
        content: "Verschlossenes Prototyp-Subraumrelais.",
        suggested: { aliases: ["Transponder"], tags: ["Technologie"], content: true },
        relations: [
          { target: "Forschungsstation 7", type: "related_to", note: "dort gefunden", suggested: true },
          { target: "Dr. Maya Chen", type: "built_by", note: "", suggested: false },
        ],
      }),
      "object",
    );

    expect(prefill.name).toBe("Resonanz-Transponder LC-89");
    expect(prefill.type).toBe("object");
    expect(prefill.aliases).toEqual(["LC-89", "Transponder"]);
    expect(prefill.tags).toEqual(["Technologie", "Relikt"]);
    expect(prefill.content).toBe("Verschlossenes Prototyp-Subraumrelais.");
    expect(prefill.suggested).toEqual({
      aliases: ["Transponder"],
      tags: ["Technologie"],
      content: true,
    });
    expect(prefill.relations).toEqual([
      { target: "Forschungsstation 7", relation_type: "related_to", note: "dort gefunden", suggested: true },
      { target: "Dr. Maya Chen", relation_type: "built_by", note: undefined, suggested: false },
    ]);
  });

  it("an empty proposal maps to an empty prefill with the session's type", () => {
    expect(entityPrefillFromProposal(null, "location")).toEqual({
      type: "location",
      relations: [],
    });
  });
});

describe("createFormState", () => {
  it("the interview locks the type", () => {
    const prefill = entityPrefillFromProposal(proposed({ name: "LC-89" }), "object");
    const interview = createFormState({ source: "interview", prefill });
    expect(interview.typeLocked).toBe(true);
    expect(interview.type).toBe("object");
    // The hand-made form owns its type box and starts empty.
    const manual = createFormState({ source: "manual" });
    expect(manual.typeLocked).toBe(false);
    expect(manual.type).toBe("");
  });

  it("an ambiguous alias offers both", () => {
    const prefill = entityPrefillFromProposal(
      proposed({
        name: "LC-89",
        relations: [{ target: "May", type: "related_to", note: "", suggested: true }],
      }),
      "object",
    );
    const rows = createFormState({ source: "interview", prefill }).relations;
    expect(rows).toHaveLength(1);
    expect(rows[0].target).toBe("May");

    const resolution = resolveRelationTarget(rows[0].target, ENTITIES);
    expect(resolution.kind).toBe("many");
    if (resolution.kind !== "many") throw new Error("expected many");
    expect(resolution.entities.map((row) => row.name)).toEqual(["Dr. Maya Chen", "ARIA"]);
  });
});

describe("a chosen ambiguity stays chosen", () => {
  // The browser leg's collision shape: «Kavic» names the location and is
  // Mira's alias. The typed word alone is ambiguous; only the explicit pick
  // says which row the writer meant.
  const KAVIC = entityRow({ id: "e5", name: "Kavic", type: "location" });
  const MIRA = entityRow({ id: "e6", name: "Mira", aliases: ["Kavic"] });
  const COLLISION = [KAVIC, MIRA];

  it("a name that is another row's alias stays many and the body drops the row", () => {
    const row = { target: "Kavic", relationType: "located_in", note: "" };
    const resolution = resolveRelationTarget(row.target, COLLISION);
    expect(resolution.kind).toBe("many");
    if (resolution.kind !== "many") throw new Error("expected many");
    expect(new Set(resolution.entities.map((entity) => entity.id))).toEqual(new Set(["e5", "e6"]));

    // No pick yet: the row is unresolved, so the save would leave it out.
    expect(relationRowOutcome(row, COLLISION)).toBe("unresolved-target");
    expect(
      buildEntityCreateBody(form({ relations: [row], entities: COLLISION })).relations,
    ).toEqual([]);
  });

  it.each([KAVIC, MIRA])(
    "the pick saves to $name even though the typed word resolves to both",
    (chosen) => {
      const row = {
        target: "Kavic",
        relationType: "located_in",
        note: "",
        chosenId: chosen.id,
      };
      expect(relationRowOutcome(row, COLLISION)).toBe("kept");
      expect(buildEntityCreateBody(form({ relations: [row], entities: COLLISION })).relations).toEqual([
        { to_entity_id: chosen.id, relation_type: "located_in", note: null },
      ]);

      // Typing the target again drops the pick: the word is ambiguous again.
      expect(relationRowOutcome({ ...row, chosenId: undefined }, COLLISION)).toBe(
        "unresolved-target",
      );
    },
  );
});
