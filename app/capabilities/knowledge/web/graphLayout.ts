/**
 * The lore graph's layout, pure (W5 Task 3): the same canon always answers
 * the same positions. The nodes take a canonical order — the case-folded
 * name first, then the id only to separate two namesakes — seed onto a
 * circle by that order, and settle through a fixed-iteration
 * Fruchterman–Reingold pass — repulsion between every pair, attraction along
 * every edge, a gentle pull to the centre, cooling each step. The writer's
 * names are the canon's identity; the server's UUIDs are fresh on every seed,
 * so ordering by them would move a re-seeded picture. No randomness anywhere:
 * a re-run, a reorder or a remount draws the identical web.
 *
 * The viewport's fit math lives here too, so the reset's answer is a pure
 * function of the bounds and the viewport — testable without an SVG.
 */

/** One node's settled position, in the layout's own coordinate space. */
export interface Point {
  x: number;
  y: number;
}

/** The box a set of positions spans. */
export interface Bounds {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

/** The viewport's transform: translate (x, y) then scale k, origin top-left. */
export interface Transform {
  x: number;
  y: number;
  k: number;
}

/** The layout reads the identity and the edges' ends — the rows' other
 *  fields are the panel's business, never the geometry's. The name is the
 *  canon's stable identity; the id is the server's, fresh on every seed. */
export interface LayoutEntity {
  id: string;
  name: string;
}
export interface LayoutRelation {
  from_entity_id: string;
  to_entity_id: string;
}

const ITERATIONS = 300;
const COOLING = 0.97;

/** The canonical key: the case-folded name, then the id. Names carry the
 *  writer's canon and stay put across a re-seed; the id is the server's fresh
 *  UUID, so it only separates two rows that share a name. Case folding is the
 *  locale-independent `toLowerCase` and the compare is by code unit, so the
 *  order is the same in every browser and every run. */
function canonicalKey(entity: LayoutEntity): [string, string] {
  return [entity.name.toLowerCase(), entity.id];
}

function compareCanonical(a: LayoutEntity, b: LayoutEntity): number {
  const [nameA, idA] = canonicalKey(a);
  const [nameB, idB] = canonicalKey(b);
  if (nameA < nameB) return -1;
  if (nameA > nameB) return 1;
  if (idA < idB) return -1;
  if (idA > idB) return 1;
  return 0;
}

function round(value: number): number {
  const rounded = Math.round(value * 100) / 100;
  // Negative zero is a float artefact of the centroid subtraction; it must
  // not distinguish two otherwise identical layouts.
  return rounded === 0 ? 0 : rounded;
}

/**
 * Settle the web. Entities are ordered by case-folded name, then id (the
 * canonical seed), placed on a circle, then relaxed. Edges whose ends are
 * absent — and self-loops, which pull a node onto itself — are skipped in the
 * force pass; the canvas still draws a self-loop, it just cannot move its
 * node.
 */
export function layoutGraph(
  entities: readonly LayoutEntity[],
  relations: readonly LayoutRelation[],
): Map<string, Point> {
  const nodes = [...entities].sort(compareCanonical);
  const positions = new Map<string, Point>();
  const n = nodes.length;
  if (n === 0) return positions;
  if (n === 1) {
    positions.set(nodes[0].id, { x: 0, y: 0 });
    return positions;
  }

  const index = new Map(nodes.map((entity, at) => [entity.id, at]));
  const radius = Math.max(140, n * 28);
  const xs = nodes.map((_, at) => radius * Math.cos((2 * Math.PI * at) / n));
  const ys = nodes.map((_, at) => radius * Math.sin((2 * Math.PI * at) / n));

  const edges: [number, number][] = [];
  for (const relation of relations) {
    const from = index.get(relation.from_entity_id);
    const to = index.get(relation.to_entity_id);
    if (from === undefined || to === undefined || from === to) continue;
    edges.push([from, to]);
  }
  // Canonical edge order: the force pass accumulates in this order, so the
  // relations' arrival order cannot perturb the float sum into a different
  // picture.
  edges.sort((a, b) => a[0] - b[0] || a[1] - b[1]);

  // The ideal spring length sits a card-width plus a gap apart, so a connected
  // pair settles with room for its edge to show between the two cards rather
  // than collapsing under them. The centre pull scales with the node count so
  // a sparse web stays compact whatever its size.
  const k = 320;
  const gravity = Math.max(1, n * 0.5);
  let temperature = radius / 10;

  for (let step = 0; step < ITERATIONS; step++) {
    const dx = new Array<number>(n).fill(0);
    const dy = new Array<number>(n).fill(0);

    // Repulsion: every pair pushes apart, inverse in their distance.
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const ox = xs[i] - xs[j];
        const oy = ys[i] - ys[j];
        const distance = Math.hypot(ox, oy) || 0.01;
        const force = (k * k) / distance;
        const fx = (ox / distance) * force;
        const fy = (oy / distance) * force;
        dx[i] += fx;
        dy[i] += fy;
        dx[j] -= fx;
        dy[j] -= fy;
      }
    }

    // Attraction: every edge pulls its ends together, growing with distance.
    for (const [from, to] of edges) {
      const ox = xs[from] - xs[to];
      const oy = ys[from] - ys[to];
      const distance = Math.hypot(ox, oy) || 0.01;
      const force = (distance * distance) / k;
      const fx = (ox / distance) * force;
      const fy = (oy / distance) * force;
      dx[from] -= fx;
      dy[from] -= fy;
      dx[to] += fx;
      dy[to] += fy;
    }

    // Gravity keeps the web from drifting off the centre.
    for (let i = 0; i < n; i++) {
      dx[i] -= xs[i] * gravity;
      dy[i] -= ys[i] * gravity;
    }

    // Apply, capped by the cooling temperature so the pass settles.
    for (let i = 0; i < n; i++) {
      const distance = Math.hypot(dx[i], dy[i]) || 0.01;
      const capped = Math.min(distance, temperature);
      xs[i] += (dx[i] / distance) * capped;
      ys[i] += (dy[i] / distance) * capped;
    }
    temperature *= COOLING;
  }

  // Re-centre on the web's own centroid so the fit math reads a tidy box.
  const cx = xs.reduce((sum, value) => sum + value, 0) / n;
  const cy = ys.reduce((sum, value) => sum + value, 0) / n;
  nodes.forEach((entity, at) => {
    positions.set(entity.id, { x: round(xs[at] - cx), y: round(ys[at] - cy) });
  });
  return positions;
}

/** The box the positions span; an empty set answers a unit box at the origin. */
export function graphBounds(points: Iterable<Point>): Bounds {
  let minX = 0;
  let minY = 0;
  let maxX = 0;
  let maxY = 0;
  let seen = false;
  for (const point of points) {
    if (!seen) {
      minX = maxX = point.x;
      minY = maxY = point.y;
      seen = true;
      continue;
    }
    minX = Math.min(minX, point.x);
    minY = Math.min(minY, point.y);
    maxX = Math.max(maxX, point.x);
    maxY = Math.max(maxY, point.y);
  }
  return { minX, minY, maxX, maxY };
}

/**
 * The transform that centres the bounds in a viewport and scales them to fit
 * inside the padding. The reset's answer: a pure function of the bounds and
 * the viewport, so a reset always returns to the identical framing. A
 * degenerate viewport or a zero-span box never divides by zero — the scale
 * floors at a sane positive value.
 */
export function fitTransform(bounds: Bounds, width: number, height: number, padding: number): Transform {
  const spanX = Math.max(bounds.maxX - bounds.minX, 1);
  const spanY = Math.max(bounds.maxY - bounds.minY, 1);
  const usableX = Math.max(width - padding * 2, 1);
  const usableY = Math.max(height - padding * 2, 1);
  const k = Math.min(usableX / spanX, usableY / spanY, 1.5);
  const centreX = (bounds.minX + bounds.maxX) / 2;
  const centreY = (bounds.minY + bounds.maxY) / 2;
  return {
    x: width / 2 - centreX * k,
    y: height / 2 - centreY * k,
    k,
  };
}

/**
 * A stable key for the SET the web draws: the entities' canonical name/id
 * keys and the sorted edge ends, each in the layout's own order. Two reads of
 * the same rows answer the same key whatever their arrival order or object
 * identity, so a background refetch of an unchanged canon does not reframe the
 * viewport — only a materially different set (a node, a rename or an edge
 * added or gone) changes the key. The separators are control characters no id
 * or name carries.
 */
export function graphSignature(
  entities: readonly LayoutEntity[],
  relations: readonly LayoutRelation[],
): string {
  const keys = [...entities]
    .sort(compareCanonical)
    .map((entity) => canonicalKey(entity).join("\u0000"));
  const edges = relations
    .map((relation) => `${relation.from_entity_id}\u0000${relation.to_entity_id}`)
    .sort((a, b) => a.localeCompare(b));
  return `${keys.join("\u0001")}\u0002${edges.join("\u0001")}`;
}
