/**
 * The lore graph's pure layout (graphLayout.ts): the same entities and
 * relations always answer the same positions — a canonical order seeded onto
 * a circle, then a fixed-iteration force pass with no randomness anywhere.
 * No React, no SVG, no requests: the geometry is testable on its own, and the
 * viewport's fit math derives from the bounds the layout answers.
 */
import { describe, expect, it } from "vitest";

import { fitTransform, graphBounds, layoutGraph, type Point } from "./graphLayout";

function entities(...ids: string[]): { id: string }[] {
  return ids.map((id) => ({ id }));
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

describe("layoutGraph — same data, same positions, no randomness", () => {
  it("answers identical positions for identical input across runs", () => {
    const first = layoutGraph(WEB, EDGES);
    const second = layoutGraph(WEB, EDGES);
    expect(positionsOf(first)).toEqual(positionsOf(second));
  });

  it("is stable under input reordering — the canonical order is the entity id", () => {
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
