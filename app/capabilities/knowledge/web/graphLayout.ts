/**
 * The graph canvas's deterministic layout: entities placed on a pure
 * function of the input, so the same novel graphs identically on every
 * render. No DOM, no `Math.random` — the only jitter source is a seeded
 * PRNG with a fixed default seed, so positions are byte-identical
 * run to run.
 */

/** One entity as the layout reads it: the `EntityRead` row's graph half. */
export interface GraphEntity {
  id: string;
  name: string;
  type: string;
}

/** One relation as the layout reads it: the `RelationRead` edge's graph half. */
export interface GraphRelation {
  id: string;
  from_entity_id: string;
  to_entity_id: string;
  relation_type: string;
}

export interface GraphViewport {
  width: number;
  height: number;
}

export interface GraphLayoutOptions {
  /** Cap on placed nodes; the rest are truncated, counted, not placed. */
  maxNodes?: number;
  /** Cap on emitted edges; the rest are truncated, counted, not drawn. */
  maxEdges?: number;
  /** The jitter PRNG's seed; fixed by default so output is deterministic. */
  seed?: number;
}

export interface GraphNode {
  id: string;
  name: string;
  type: string;
  x: number;
  y: number;
}

export interface GraphEdge {
  id: string;
  from: string;
  to: string;
  relationType: string;
}

export interface GraphLayout {
  nodes: GraphNode[];
  edges: GraphEdge[];
  width: number;
  height: number;
  /** The input's entity count, before truncation — the showing note's "of M". */
  totalNodes: number;
  /** The input's relation count, before truncation. */
  totalEdges: number;
  shownNodes: number;
  shownEdges: number;
}

const DEFAULT_SEED = 0x2f6e2b1;

/**
 * A mulberry32 seeded PRNG: deterministic per seed, with no shared state —
 * each layout call builds its own, so call order cannot leak into output.
 */
function mulberry32(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let mixed = state;
    mixed = Math.imul(mixed ^ (mixed >>> 15), mixed | 1);
    mixed ^= mixed + Math.imul(mixed ^ (mixed >>> 7), mixed | 61);
    return ((mixed ^ (mixed >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Lay `entities` and `relations` out inside `viewport`: nodes group into one
 * column band per entity type (types sorted by name, nodes by id within),
 * each band's nodes stack on a grid down its centre, and a seeded jitter
 * (bounded by the cell padding, so no node can leave the box) keeps
 * same-type neighbours from sitting exactly atop each other's row line.
 * Nodes beyond `maxNodes` are cut by (type, id) order, edges whose ends were
 * cut — or that fall beyond `maxEdges` — are cut by
 * (from, to, relation_type, id) order, and both cuts are counted for the
 * page's "showing N of M" note.
 */
export function layoutGraph(
  entities: GraphEntity[],
  relations: GraphRelation[],
  viewport: GraphViewport,
  options: GraphLayoutOptions = {},
): GraphLayout {
  const { maxNodes = 120, maxEdges = 200, seed = DEFAULT_SEED } = options;
  const { width, height } = viewport;

  const ordered = [...entities].sort(
    (a, b) => a.type.localeCompare(b.type) || a.id.localeCompare(b.id),
  );
  const kept = ordered.slice(0, Math.max(0, maxNodes));
  const placed = new Map(kept.map((entity) => [entity.id, entity]));

  const orderedEdges = [...relations]
    .filter((relation) => placed.has(relation.from_entity_id) && placed.has(relation.to_entity_id))
    .sort(
      (a, b) =>
        a.from_entity_id.localeCompare(b.from_entity_id) ||
        a.to_entity_id.localeCompare(b.to_entity_id) ||
        a.relation_type.localeCompare(b.relation_type) ||
        a.id.localeCompare(b.id),
    );
  const keptEdges = orderedEdges.slice(0, Math.max(0, maxEdges));

  const types = [...new Set(kept.map((entity) => entity.type))].sort((a, b) =>
    a.localeCompare(b),
  );
  const padding = 48;
  const innerWidth = Math.max(1, width - padding * 2);
  const innerHeight = Math.max(1, height - padding * 2);
  const random = mulberry32(seed);

  const nodes: GraphNode[] = [];
  types.forEach((type, band) => {
    const members = kept.filter((entity) => entity.type === type);
    const bandX =
      types.length === 1
        ? padding + innerWidth / 2
        : padding + (innerWidth * band) / (types.length - 1);
    members.forEach((entity, row) => {
      const rowY =
        members.length === 1
          ? padding + innerHeight / 2
          : padding + (innerHeight * row) / (members.length - 1);
      // The jitter stays inside half the cell margin: with one member the
      // cell is the whole band, so clamp to a fixed ±10 box instead.
      const spanX = types.length === 1 ? 20 : innerWidth / (types.length - 1) / 2 - 4;
      const spanY = members.length === 1 ? 20 : innerHeight / (members.length - 1) / 2 - 4;
      const clamp = (span: number): number => Math.max(0, Math.min(span, innerWidth / 2 - 1, innerHeight / 2 - 1));
      const x = Math.min(Math.max(bandX + (random() - 0.5) * 2 * clamp(spanX), 0), width);
      const y = Math.min(Math.max(rowY + (random() - 0.5) * 2 * clamp(spanY), 0), height);
      nodes.push({ id: entity.id, name: entity.name, type: entity.type, x, y });
    });
  });
  nodes.sort((a, b) => a.id.localeCompare(b.id));

  const edges: GraphEdge[] = keptEdges.map((relation) => ({
    id: relation.id,
    from: relation.from_entity_id,
    to: relation.to_entity_id,
    relationType: relation.relation_type,
  }));

  return {
    nodes,
    edges,
    width,
    height,
    totalNodes: entities.length,
    totalEdges: relations.length,
    shownNodes: nodes.length,
    shownEdges: edges.length,
  };
}
