import { describe, expect, it } from "vitest";

import { layoutGraph } from "./graphLayout";
import type { GraphEntity, GraphRelation } from "./graphLayout";

/**
 * The fixed seed graph: 5 entities over 2 types, 4 relations including a
 * cycle (a → b → c → a) and an isolated node (e, no edges). The layout must
 * be deterministic — the same input twice gives byte-identical positions —
 * keep every node inside the viewport, place the isolated node rather than
 * dropping it, and only emit edges whose ends exist.
 */
const entities: GraphEntity[] = [
  { id: "e-a", name: "Aster", type: "character" },
  { id: "e-b", name: "Bram", type: "character" },
  { id: "e-c", name: "Cinderhold", type: "location" },
  { id: "e-d", name: "Dunmere", type: "location" },
  { id: "e-e", name: "Edda", type: "character" },
];

const relations: GraphRelation[] = [
  { id: "r-1", from_entity_id: "e-a", to_entity_id: "e-b", relation_type: "ally_of" },
  { id: "r-2", from_entity_id: "e-b", to_entity_id: "e-c", relation_type: "located_in" },
  { id: "r-3", from_entity_id: "e-c", to_entity_id: "e-a", relation_type: "inhabits" },
  { id: "r-4", from_entity_id: "e-a", to_entity_id: "e-d", relation_type: "owns" },
];

const VIEW = { width: 800, height: 600 };

describe("layoutGraph determinism", () => {
  it("gives byte-identical positions for the same input, run twice", () => {
    const first = layoutGraph(entities, relations, VIEW);
    const second = layoutGraph(entities, relations, VIEW);
    expect(second).toEqual(first);
    expect(second.nodes.map((n) => [n.x, n.y])).toEqual(
      first.nodes.map((n) => [n.x, n.y]),
    );
  });

  it("keeps every node inside the viewport box", () => {
    const graph = layoutGraph(entities, relations, VIEW);
    expect(graph.nodes).toHaveLength(5);
    for (const node of graph.nodes) {
      expect(node.x).toBeGreaterThanOrEqual(0);
      expect(node.x).toBeLessThanOrEqual(VIEW.width);
      expect(node.y).toBeGreaterThanOrEqual(0);
      expect(node.y).toBeLessThanOrEqual(VIEW.height);
    }
  });

  it("places the isolated node instead of dropping it", () => {
    const graph = layoutGraph(entities, relations, VIEW);
    const edda = graph.nodes.find((n) => n.id === "e-e");
    expect(edda).toBeDefined();
    expect(Number.isFinite(edda!.x)).toBe(true);
    expect(Number.isFinite(edda!.y)).toBe(true);
  });

  it("only emits edges whose ends are placed nodes", () => {
    const graph = layoutGraph(entities, relations, VIEW);
    const ids = new Set(graph.nodes.map((n) => n.id));
    expect(graph.edges.length).toBeGreaterThan(0);
    for (const edge of graph.edges) {
      expect(ids.has(edge.from)).toBe(true);
      expect(ids.has(edge.to)).toBe(true);
    }
  });
});

describe("layoutGraph edge cases", () => {
  it("maps empty input to empty nodes/edges with zero totals", () => {
    const graph = layoutGraph([], [], VIEW);
    expect(graph.nodes).toEqual([]);
    expect(graph.edges).toEqual([]);
    expect(graph.totalNodes).toBe(0);
    expect(graph.totalEdges).toBe(0);
    expect(graph.shownNodes).toBe(0);
    expect(graph.shownEdges).toBe(0);
  });

  it("places a single node of a single type, finite and inside the viewport", () => {
    const graph = layoutGraph(
      [{ id: "e-solo", name: "Solo", type: "character" }],
      [],
      VIEW,
    );
    expect(graph.nodes).toHaveLength(1);
    expect(graph.edges).toEqual([]);
    expect(graph.totalNodes).toBe(1);
    const [solo] = graph.nodes;
    expect(Number.isFinite(solo.x)).toBe(true);
    expect(Number.isFinite(solo.y)).toBe(true);
    expect(solo.x).toBeGreaterThanOrEqual(0);
    expect(solo.x).toBeLessThanOrEqual(VIEW.width);
    expect(solo.y).toBeGreaterThanOrEqual(0);
    expect(solo.y).toBeLessThanOrEqual(VIEW.height);
  });

  it("emits a self-loop edge with from equal to to when the node is present", () => {
    const graph = layoutGraph(
      [{ id: "e-solo", name: "Solo", type: "character" }],
      [
        {
          id: "r-loop",
          from_entity_id: "e-solo",
          to_entity_id: "e-solo",
          relation_type: "reflects_on",
        },
      ],
      VIEW,
    );
    expect(graph.edges).toHaveLength(1);
    expect(graph.edges[0].from).toBe("e-solo");
    expect(graph.edges[0].to).toBe("e-solo");
  });

  it("drops genuinely dangling refs while keeping edges whose ends exist", () => {
    const graph = layoutGraph(
      entities,
      [
        ...relations,
        {
        id: "r-ghost",
        from_entity_id: "e-a",
        to_entity_id: "e-never-there",
        relation_type: "haunts",
      },
      {
        id: "r-phantom",
        from_entity_id: "e-no-such",
        to_entity_id: "e-also-missing",
          relation_type: "haunts",
        },
      ],
      VIEW,
    );
    expect(graph.edges.map((edge) => edge.id)).not.toContain("r-ghost");
    expect(graph.edges.map((edge) => edge.id)).not.toContain("r-phantom");
    expect(graph.totalEdges).toBe(relations.length + 2);
    expect(graph.shownEdges).toBe(relations.length);
    const ids = new Set(graph.nodes.map((n) => n.id));
    for (const edge of graph.edges) {
      expect(ids.has(edge.from)).toBe(true);
      expect(ids.has(edge.to)).toBe(true);
    }
  });
});

describe("layoutGraph truncation", () => {
  it("caps nodes and edges and reports the totals for the showing note", () => {
    const graph = layoutGraph(entities, relations, VIEW, { maxNodes: 3, maxEdges: 2 });
    expect(graph.nodes).toHaveLength(3);
    expect(graph.edges.length).toBeLessThanOrEqual(2);
    expect(graph.totalNodes).toBe(5);
    expect(graph.totalEdges).toBe(4);
    expect(graph.shownNodes).toBe(3);
    expect(graph.shownEdges).toBe(graph.edges.length);
  });

  it("drops edges whose ends were truncated away", () => {
    const graph = layoutGraph(entities, relations, VIEW, { maxNodes: 2, maxEdges: 10 });
    const ids = new Set(graph.nodes.map((n) => n.id));
    for (const edge of graph.edges) {
      expect(ids.has(edge.from)).toBe(true);
      expect(ids.has(edge.to)).toBe(true);
    }
  });
});
