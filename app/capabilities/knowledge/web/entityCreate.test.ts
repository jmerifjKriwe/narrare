/**
 * The create dialog's pure seam: resolving a typed relation target against
 * the novel's roster, spotting a name that already exists, and turning the
 * form into the POST body. Rows the novel cannot resolve to exactly one
 * entity are left out of the body — the dialog tells the writer so, and a
 * guessed edge would be worse than none.
 */
import { describe, expect, it } from "vitest";

import type { Entity } from "@shell/lib/api/client";

import {
  buildEntityCreateBody,
  findDuplicateName,
  resolveRelationTarget,
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
});
