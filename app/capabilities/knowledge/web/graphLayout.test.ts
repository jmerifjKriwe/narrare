/**
 * The lore graph's pure layout (graphLayout.ts): the same entities and
 * relations always answer the same positions — a canonical order seeded onto
 * a circle, then a fixed-iteration force pass with no randomness anywhere.
 * No React, no SVG, no requests: the geometry is testable on its own, and the
 * viewport's fit math derives from the bounds the layout answers.
 */
import { describe, expect, it } from "vitest";

import { fitTransform, graphBounds, graphSignature, layoutGraph, type Point } from "./graphLayout";

function entities(...names: string[]): { id: string; name: string }[] {
  // The name is the canonical key; these rows keep the old pin's id equal to
  // the name so a short, readable web stays readable.
  return names.map((name) => ({ id: name, name }));
}

function edge(from: string, to: string): { from_entity_id: string; to_entity_id: string } {
  return { from_entity_id: from, to_entity_id: to };
}

/** A small web: four nodes, a chain plus one cross edge. */
const WEB = entities("a", "b", "c", "d");
const EDGES = [edge("a", "b"), edge("b", "c"), edge("c", "d"), edge("a", "d")];

function positionsOf(layout: Map<string, Point>): [string, Point][] {
  return [...layout.entries()].sort(([x], [y]) => (x < y ? -1 : x > y ? 1 : 0));
}

/** The same rows keyed by their names — the seat a reader sees on the card,
 *  never the server's fresh UUID. */
function byName(
  layout: Map<string, Point>,
  rows: readonly { id: string; name: string }[],
): Record<string, Point | undefined> {
  return Object.fromEntries(rows.map((row) => [row.name, layout.get(row.id)]));
}

/** Edges named by their ends, resolved to whichever ids this canon carries. */
function namedEdges(
  rows: readonly { id: string; name: string }[],
  ...pairs: [string, string][]
): { from_entity_id: string; to_entity_id: string }[] {
  const idOf = new Map(rows.map((row) => [row.name, row.id]));
  return pairs.map(([from, to]) => edge(idOf.get(from)!, idOf.get(to)!));
}

/** One canon under two sets of fresh, UUID-shaped ids — the API's own shape. */
const FRESH_A = [
  { id: "6f1c9e2a-3b4d-4c5e-8f60-71a2b3c4d5e6", name: "Mira" },
  { id: "9a8b7c6d-5e4f-4a3b-9c2d-1e0f3a4b5c6d", name: "Kavic" },
  { id: "0d1e2f3a-4b5c-4d6e-8f90-a1b2c3d4e5f6", name: "Vulkan" },
];
const FRESH_B = [
  { id: "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d", name: "Mira" },
  { id: "2b3c4d5e-6f7a-4b8c-9d0e-1f2a3b4c5d6e", name: "Kavic" },
  { id: "3c4d5e6f-7a8b-4c9d-8e1f-2a3b4c5d6e7f", name: "Vulkan" },
];
const CHAIN: [string, string][] = [
  ["Mira", "Kavic"],
  ["Kavic", "Vulkan"],
];

describe("layoutGraph — same data, same positions, no randomness", () => {
  it("answers identical positions for identical input across runs", () => {
    const first = layoutGraph(WEB, EDGES);
    const second = layoutGraph(WEB, EDGES);
    expect(positionsOf(first)).toEqual(positionsOf(second));
  });

  it("is stable under input reordering — the canonical order is the entity name", () => {
    const shuffled = entities("d", "b", "a", "c");
    const reversedEdges = [...EDGES].reverse();
    expect(positionsOf(layoutGraph(shuffled, reversedEdges))).toEqual(
      positionsOf(layoutGraph(WEB, EDGES)),
    );
  });

  it("places every node at a finite coordinate", () => {
    const layout = layoutGraph(WEB, EDGES);
    expect(layout.size).toBe(4);
    for (const point of layout.values()) {
      expect(Number.isFinite(point.x)).toBe(true);
      expect(Number.isFinite(point.y)).toBe(true);
    }
  });

  it("an empty canon answers an empty layout", () => {
    expect(layoutGraph([], []).size).toBe(0);
  });

  it("a lone node stands at the centre", () => {
    const layout = layoutGraph(entities("solo"), []);
    expect(layout.get("solo")).toEqual({ x: 0, y: 0 });
  });

  it("an edge pulls its ends nearer than repulsion alone would leave them", () => {
    const connected = layoutGraph(entities("a", "b"), [edge("a", "b")]);
    const apart = layoutGraph(entities("a", "b"), []);
    const distance = (layout: Map<string, Point>) => {
      const a = layout.get("a")!;
      const b = layout.get("b")!;
      return Math.hypot(a.x - b.x, a.y - b.y);
    };
    expect(distance(connected)).toBeGreaterThan(0);
    expect(distance(connected)).toBeLessThan(distance(apart));
  });

  it("ignores edges whose ends are absent and self-loops in the force pass", () => {
    const withStrays = layoutGraph(entities("a", "b"), [
      edge("a", "b"),
      edge("a", "ghost"),
      edge("a", "a"),
    ]);
    const clean = layoutGraph(entities("a", "b"), [edge("a", "b")]);
    expect(positionsOf(withStrays)).toEqual(positionsOf(clean));
  });

  it("a larger web stays deterministic and finite", () => {
    const many = entities(...Array.from({ length: 24 }, (_, i) => `n${i}`));
    const ring = many.map((e, i) => edge(e.id, many[(i + 1) % many.length].id));
    const first = layoutGraph(many, ring);
    const second = layoutGraph(many, ring);
    expect(positionsOf(first)).toEqual(positionsOf(second));
    for (const point of first.values()) {
      expect(Number.isFinite(point.x)).toBe(true);
      expect(Number.isFinite(point.y)).toBe(true);
    }
  });
});

describe("layoutGraph — the canon's names are the key, never the server's UUIDs (#978)", () => {
  it("identical names settle identically under two sets of fresh UUIDs", () => {
    const first = layoutGraph(FRESH_A, namedEdges(FRESH_A, ...CHAIN));
    const second = layoutGraph(FRESH_B, namedEdges(FRESH_B, ...CHAIN));
    expect(byName(second, FRESH_B)).toEqual(byName(first, FRESH_A));
  });

  it("the rows' arrival order cannot move a single card", () => {
    const forward = layoutGraph(FRESH_A, namedEdges(FRESH_A, ...CHAIN));
    const reversed = [...FRESH_A].reverse();
    const reversedEdges = namedEdges(FRESH_A, ...CHAIN).reverse();
    expect(byName(layoutGraph(reversed, reversedEdges), reversed)).toEqual(byName(forward, FRESH_A));
  });

  it("orders names case-insensitively — the capital's shift moves nothing", () => {
    // The ids stand in the OPPOSITE order to the case-folded names in the
    // second canon: only a folded name key answers the same seats.
    const lower = [
      { id: "z-id", name: "Zebra" },
      { id: "a-id", name: "apple" },
    ];
    const upper = [
      { id: "a-id", name: "zebra" },
      { id: "z-id", name: "Apple" },
    ];
    const seats = (rows: readonly { id: string; name: string }[]) => {
      const layout = layoutGraph(rows, [edge(rows[0].id, rows[1].id)]);
      return Object.fromEntries(rows.map((row) => [row.name.toLowerCase(), layout.get(row.id)]));
    };
    // Under a raw, case-sensitive compare the two canons disagree: "Zebra"
    // sorts before "apple", while "Apple" sorts before "zebra".
    expect(seats(upper)).toEqual(seats(lower));
  });

  it("separates duplicate names by id, whatever their arrival order", () => {
    const rows = [
      { id: "aaaaaaaa-1111-4111-8111-111111111111", name: "Mira" },
      { id: "bbbbbbbb-2222-4222-8222-222222222222", name: "Mira" },
      { id: "cccccccc-3333-4333-8333-333333333333", name: "Kavic" },
    ];
    const relations = [edge(rows[0].id, rows[2].id), edge(rows[1].id, rows[2].id)];
    const layout = layoutGraph(rows, relations);
    const reversed = [...rows].reverse();
    const reversedLayout = layoutGraph(reversed, [...relations].reverse());
    for (const row of rows) {
      expect(reversedLayout.get(row.id)).toEqual(layout.get(row.id));
    }
    // The two namesakes are two seats, not one collapsed row.
    expect(layout.get(rows[0].id)).not.toEqual(layout.get(rows[1].id));
  });
});

describe("graphBounds — the box the positions span", () => {
  it("bounds the layout's extremes", () => {
    const layout = layoutGraph(WEB, EDGES);
    const bounds = graphBounds(layout.values());
    for (const point of layout.values()) {
      expect(point.x).toBeGreaterThanOrEqual(bounds.minX);
      expect(point.x).toBeLessThanOrEqual(bounds.maxX);
      expect(point.y).toBeGreaterThanOrEqual(bounds.minY);
      expect(point.y).toBeLessThanOrEqual(bounds.maxY);
    }
  });

  it("an empty set answers a unit box at the origin", () => {
    expect(graphBounds([])).toEqual({ minX: 0, minY: 0, maxX: 0, maxY: 0 });
  });
});

describe("fitTransform — centre the bounds in the viewport, honestly resettable", () => {
  const bounds = { minX: -100, minY: -50, maxX: 100, maxY: 50 };

  it("centres the bounds and scales them to fit with padding", () => {
    const view = fitTransform(bounds, 800, 600, 48);
    // The bounds' centre (0,0) lands at the viewport's centre.
    expect(view.x).toBeCloseTo(400, 5);
    expect(view.y).toBeCloseTo(300, 5);
    expect(view.k).toBeGreaterThan(0);
    // The scaled box fits inside the padded viewport.
    expect(200 * view.k).toBeLessThanOrEqual(800 - 2 * 48 + 1e-6);
    expect(100 * view.k).toBeLessThanOrEqual(600 - 2 * 48 + 1e-6);
  });

  it("is a pure function of bounds and viewport — the reset's own answer", () => {
    expect(fitTransform(bounds, 800, 600, 48)).toEqual(fitTransform(bounds, 800, 600, 48));
  });

  it("a degenerate viewport never divides by zero", () => {
    const view = fitTransform(bounds, 0, 0, 48);
    expect(Number.isFinite(view.k)).toBe(true);
    expect(view.k).toBeGreaterThan(0);
  });

  it("a zero-span box (one node) still answers a sane scale", () => {
    const view = fitTransform({ minX: 0, minY: 0, maxX: 0, maxY: 0 }, 800, 600, 48);
    expect(Number.isFinite(view.k)).toBe(true);
    expect(view.k).toBeGreaterThan(0);
    expect(view.x).toBeCloseTo(400, 5);
    expect(view.y).toBeCloseTo(300, 5);
  });
});

describe("graphSignature — the set's stable key, the refetch's reframe guard", () => {
  it("the same rows answer the same key whatever their order or identity", () => {
    const fresh = entities("d", "c", "b", "a");
    const freshEdges = [...EDGES].reverse();
    expect(graphSignature(fresh, freshEdges)).toBe(graphSignature(WEB, EDGES));
    // Fresh objects, identical rows — a refetch's new array, the same set.
    const cloned = WEB.map((entity) => ({ ...entity }));
    const clonedEdges = EDGES.map((relation) => ({ ...relation }));
    expect(graphSignature(cloned, clonedEdges)).toBe(graphSignature(WEB, EDGES));
  });

  it("a node added or gone changes the key", () => {
    const base = graphSignature(WEB, EDGES);
    expect(graphSignature([...WEB, { id: "e", name: "Echo" }], EDGES)).not.toBe(base);
    expect(graphSignature(WEB.slice(1), EDGES)).not.toBe(base);
  });

  it("a rename changes the key — the layout key is the name, then the id", () => {
    const renamed = [{ id: "e1", name: "Kavic" }];
    expect(graphSignature(renamed, [])).not.toBe(graphSignature([{ id: "e1", name: "Mira" }], []));
    // The same canonical key in another arrival order is the same set.
    const rows = [
      { id: "e2", name: "Mira" },
      { id: "e1", name: "Kavic" },
    ];
    expect(graphSignature([...rows].reverse(), [])).toBe(graphSignature(rows, []));
  });

  it("an edge added or gone changes the key", () => {
    const base = graphSignature(WEB, EDGES);
    expect(graphSignature(WEB, [...EDGES, edge("b", "d")])).not.toBe(base);
    expect(graphSignature(WEB, EDGES.slice(1))).not.toBe(base);
  });

  it("an empty set has its own stable key", () => {
    expect(graphSignature([], [])).toBe(graphSignature([], []));
    expect(graphSignature([], [])).not.toBe(graphSignature(WEB, EDGES));
  });
});
