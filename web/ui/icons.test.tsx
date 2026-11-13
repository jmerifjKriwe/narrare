// @vitest-environment jsdom
/**
 * The icon set's contract, pinned as records rather than single samples:
 * `icons` carries exactly the forty-seven names (the wave's whole vocabulary
 * — a name that drifts in or out breaks a P9 consumer), and every one of
 * them renders through `Icon` as the same hidden 16×16 svg — stroked in
 * the ink around it, filled with nothing, sized by `size` alone. The
 * drawings themselves are geometry: a glyph that renders no shape, or
 * draws its metaphor as text, cannot do its job at 16 px.
 */
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Icon, icons, type IconName } from "./icons";

/**
 * The forty-seven names, verbatim: the set is exactly this and no more.
 *
 * The first eighteen are the app's own vocabulary (the library, the
 * editor, the knowledge base, the chat, the settings, the shell's
 * rails and their marks). The twenty-nine that follow are the drafted
 * concepts the Literary Modernism screens introduce — deviation #1
 * (spec §6.9): the drafts speak in Material Symbols, the app keeps its
 * own hand-drawn faces, and a Material name pins only the *concept*.
 */
const THE_SET = [
  "books",
  "write",
  "knowledge",
  "chat",
  "settings",
  "focus",
  "railHide",
  "railShow",
  "close",
  "export",
  "import",
  "search",
  "plus",
  "check",
  "cross",
  "chevronDown",
  "selectChevron",
  "planning",
  // The drafted concepts.
  "autoStories",
  "bookmarkCollection",
  "checkCircle",
  "clock",
  "dragIndicator",
  "editNote",
  "foggy",
  "globe",
  "gridView",
  "historyEdu",
  "house",
  "hub",
  "inkHighlighter",
  "insights",
  "localFire",
  "menuBook",
  "moreHoriz",
  "neurology",
  "person",
  "radar",
  "ring",
  "schema",
  "spark",
  "target",
  "theme",
  "tune",
  "unfoldMore",
  "viewList",
  "waves",
] as const satisfies readonly IconName[];

/** Every attribute a rendered glyph carries, with its pinned value at the default size. */
const SVG_CONTRACT = {
  "aria-hidden": "true",
  viewBox: "0 0 16 16",
  width: "16",
  height: "16",
  fill: "none",
  stroke: "currentColor",
  "stroke-width": "1.5",
  "stroke-linecap": "round",
  "stroke-linejoin": "round",
} as const;

/** The svg one glyph renders as; throws naming the glyph when none renders. */
function svgOf(name: IconName, size?: number): SVGSVGElement {
  const { container } = render(<Icon name={name} size={size} />);
  const svg = container.querySelector("svg");
  if (!svg) throw new Error(`${name} renders no svg`);
  return svg;
}

/** The contract attributes of one glyph, keyed as the svg carries them. */
function contractOf(name: IconName, size?: number): Record<string, string | null> {
  const svg = svgOf(name, size);
  return Object.fromEntries(
    Object.keys(SVG_CONTRACT).map((attribute) => [attribute, svg.getAttribute(attribute)]),
  );
}

/**
 * The envelope every drawing stays inside, the one the set's doc comment
 * states: knowledge's stack sets both extremes (its ellipse tops out at
 * 2.35, its lower arc bottoms out at 13.65). The 1.5 stroke reaches 0.75
 * past the ink, so this envelope is what keeps every glyph clear of the
 * viewBox on all four sides.
 */
const BOX_MIN = 2.35;
const BOX_MAX = 13.65;

/**
 * The ink one rotation-0 arc can reach, as values the box pass can check.
 * Circular (`rx === ry`): the arc lies on its circle, so the true centre —
 * picked from the two bisector candidates by the flags, the way SVG
 * resolves them — bounds it at centre ± radius. An axis-aligned chord that
 * is a diameter: the arc is a half-ellipse, and its ink reaches exactly the
 * chord shifted by the cross-axis radius. A shorter chord is refused: a
 * major arc over it can reach farther than the chord-extent bound shows,
 * and full ellipse resolution is not work this set asks for. Anything the
 * pass cannot bound honestly fails loudly instead.
 */
function arcInk(from: readonly [number, number], p: number[]): number[] {
  const [rx, ry, rotation, large, sweep, x2, y2] = p;
  const [x1, y1] = from;
  if (rotation !== 0) throw new Error("arc rotated — the box pass reads rotation-0 arcs only");
  if (rx === ry) {
    const mx = (x1 + x2) / 2;
    const my = (y1 + y2) / 2;
    const dx = x2 - x1;
    const dy = y2 - y1;
    const half = Math.hypot(dx, dy) / 2;
    if (rx < half) throw new Error("arc radius smaller than half its chord");
    const h = Math.sqrt(rx * rx - half * half);
    const nx = half === 0 ? 0 : dy / (half * 2);
    const ny = half === 0 ? 0 : -dx / (half * 2);
    for (const sign of [1, -1]) {
      const cx = mx + sign * h * nx;
      const cy = my + sign * h * ny;
      const a1 = Math.atan2(y1 - cy, x1 - cx);
      const a2 = Math.atan2(y2 - cy, x2 - cx);
      let delta = a2 - a1;
      if (sweep === 1) while (delta <= 0) delta += 2 * Math.PI;
      else while (delta >= 0) delta -= 2 * Math.PI;
      if (Math.abs(delta) > Math.PI === (large === 1)) {
        return [cx - rx, cx + rx, cy - rx, cy + rx];
      }
    }
    throw new Error("arc centre unresolved");
  }
  if (y1 === y2) {
    if (Math.abs(Math.abs(x2 - x1) - 2 * rx) > 1e-9) {
      throw new Error("elliptical arc chord is not a diameter — its reach is not bounded by the chord");
    }
    return [Math.min(x1, x2), Math.max(x1, x2), y1 - ry, y1 + ry];
  }
  if (x1 === x2) {
    if (Math.abs(Math.abs(y2 - y1) - 2 * ry) > 1e-9) {
      throw new Error("elliptical arc chord is not a diameter — its reach is not bounded by the chord");
    }
    return [x1 - rx, x1 + rx, Math.min(y1, y2), Math.max(y1, y2)];
  }
  throw new Error("arc neither circular nor axis-aligned — cannot bound it");
}

/**
 * The geometry values one path's `d` carries, walked command by command:
 * positions from M/L/H/V/C/Q, and arcs through `arcInk` (an arc's rotation
 * and flags are parameters, its radii are sizes — none of them is a
 * coordinate, so none enters the scan as one). Relative commands are
 * refused loudly rather than mis-scanned as absolutes, and so are S/T:
 * their first control point is a reflection the tokens never carry.
 */
function pathInk(d: string): number[] {
  if (/[mlhvcsqta]/.test(d)) {
    throw new Error("path draws with relative commands — the box pass reads absolutes only");
  }
  const tokens = d.match(/[A-Za-z]|-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?/g) ?? [];
  const ARITY: Record<string, number> = { M: 2, L: 2, H: 1, V: 1, C: 6, S: 4, Q: 4, T: 2, A: 7, Z: 0 };
  const values: number[] = [];
  let pen: [number, number] = [0, 0];
  let start: [number, number] = [0, 0];
  let command = "";
  let i = 0;
  while (i < tokens.length) {
    if (/[A-Za-z]/.test(tokens[i])) {
      command = tokens[i];
      i += 1;
      if (command === "Z") {
        pen = start;
        continue;
      }
      continue;
    }
    const arity = ARITY[command];
    if (arity === undefined) {
      throw new Error(`path uses a command the box pass does not read: ${command}`);
    }
    if (arity === 0) {
      // Z takes no numbers; tokens here would loop the walk forever.
      throw new Error(`stray token where Z takes none: ${d}`);
    }
    const p = tokens.slice(i, i + arity).map(Number);
    if (p.length < arity) throw new Error(`path ends mid-command: ${d}`);
    switch (command) {
      case "M":
        pen = [p[0], p[1]];
        start = pen;
        values.push(p[0], p[1]);
        break;
      case "L":
        pen = [p[0], p[1]];
        values.push(p[0], p[1]);
        break;
      case "H":
        pen = [p[0], pen[1]];
        values.push(p[0]);
        break;
      case "V":
        pen = [pen[0], p[0]];
        values.push(p[0]);
        break;
      case "C":
      case "Q":
        pen = [p[p.length - 2], p[p.length - 1]];
        values.push(...p);
        break;
      case "S":
      case "T":
        // Their first control point is a reflection of the previous
        // command's — geometry the tokens never carry, so the scan would
        // under-count the hull it promises to bound.
        throw new Error("path draws with S/T — their reflected control point never enters the scan");
      case "A":
        values.push(...arcInk(pen, p));
        pen = [p[5], p[6]];
        break;
    }
    i += arity;
  }
  return values;
}

/** The geometry values one rendered glyph carries — paths walked, shapes as their full ink. */
function geometryValues(svg: SVGSVGElement): number[] {
  const values: number[] = [];
  for (const shape of svg.querySelectorAll("path, circle, ellipse")) {
    const cx = Number(shape.getAttribute("cx"));
    const cy = Number(shape.getAttribute("cy"));
    const r = shape.getAttribute("r");
    if (r !== null) {
      values.push(cx - Number(r), cx + Number(r), cy - Number(r), cy + Number(r));
      continue;
    }
    const rx = shape.getAttribute("rx");
    const ry = shape.getAttribute("ry");
    if (rx !== null && ry !== null) {
      values.push(cx - Number(rx), cx + Number(rx), cy - Number(ry), cy + Number(ry));
      continue;
    }
    const d = shape.getAttribute("d");
    if (d === null || d.trim() === "") throw new Error("path with no drawing data");
    values.push(...pathInk(d));
  }
  return values;
}

afterEach(cleanup);

describe("icons", () => {
  it("carries exactly the forty-seven names of the set, verbatim", () => {
    expect(Object.keys(icons).sort()).toEqual([...THE_SET].sort());
  });

  it("renders every name as the same hidden 16×16 stroked svg", () => {
    expect(Object.fromEntries(THE_SET.map((name) => [name, contractOf(name)]))).toEqual(
      Object.fromEntries(THE_SET.map((name) => [name, SVG_CONTRACT])),
    );
  });

  it("scales width and height with size, together — the grid never stretches", () => {
    expect(contractOf("search", 20)).toEqual({ ...SVG_CONTRACT, width: "20", height: "20" });
  });

  it("draws every glyph as geometry, never as text or a fill", () => {
    // Shape first: a glyph with no drawing element renders as empty space.
    expect(
      THE_SET.filter(
        (name) =>
          svgOf(name).querySelector(
            "path, circle, ellipse, line, polyline, polygon, rect",
          ) === null,
      ),
    ).toEqual([]);
    // Then the bans: no glyph may write its metaphor, and any fill there is must be none.
    expect(THE_SET.filter((name) => svgOf(name).querySelector("text") !== null)).toEqual([]);
    expect(
      THE_SET.filter((name) =>
        [...svgOf(name).querySelectorAll("[fill]")].some(
          (element) => element.getAttribute("fill") !== "none",
        ),
      ),
    ).toEqual([]);
  });

  it("keeps all forty-seven drawings distinct — cross dismisses, close folds a panel", () => {
    // cross and close must never converge on the same ✕: a dismissal drops
    // content, a close folds a panel away — and no two names may share a drawing.
    expect(new Set(THE_SET.map((name) => JSON.stringify(icons[name]))).size).toBe(47);
    expect(icons.close).not.toEqual(icons.cross);
  });

  it("draws the prompt bar's drafted concepts — the spark asks, the brain advises", () => {
    // Task 9's pair: the drafted `spark` on the Weiterschreiben trigger is
    // one closed four-pointed star, concave sides — pinned as data, like
    // the rail's grip. The drafted `neurology` on the style chip reads by
    // its cleft: the bumpy outline and the one line between hemispheres.
    const spark = svgOf("spark");
    expect(spark.querySelector("path")!.getAttribute("d")).toBe(
      "M8 2.6C8.6 5.3 10.7 7.4 13.4 8C10.7 8.6 8.6 10.7 8 13.4C7.4 10.7 5.3 8.6 2.6 8C5.3 7.4 7.4 5.3 8 2.6Z",
    );
    const brain = svgOf("neurology");
    const paths = brain.querySelectorAll("path");
    expect(paths.length).toBe(2);
    expect(paths[1]!.getAttribute("d")).toBe("M8 3.6V12.2");
  });

  it("draws the rail's grip as the drafted six dots, moved out of the row", () => {
    // Task 5 drew the row grip locally; the drawing belongs to the set the
    // same voice the rest of the wave speaks — one geometry, one consumer.
    // The owner's fix round pins the full dots the draft prints: solid
    // discs, a 0.5 circle the set's 1.5 stroke swallows whole — the hairline
    // caps read finer than the draft's ~2.5 px dots.
    const svg = svgOf("dragIndicator");
    const dots = [...svg.querySelectorAll("circle")];
    expect(
      dots.map((dot) => `${dot.getAttribute("cx")},${dot.getAttribute("cy")} r${dot.getAttribute("r")}`),
    ).toEqual([
      "5.5,4 r0.5",
      "10.5,4 r0.5",
      "5.5,8 r0.5",
      "10.5,8 r0.5",
      "5.5,12 r0.5",
      "10.5,12 r0.5",
    ]);
  });

  it("draws every glyph with real ink — no empty path, no degenerate shape", () => {
    // An empty `d` passes the shape query above while drawing nothing, and
    // a zero radius draws nothing either: the pin is the data, not the query.
    for (const name of THE_SET) {
      const shapes = [...svgOf(name).querySelectorAll("path, circle, ellipse")];
      expect(shapes.length, name).toBeGreaterThan(0);
      for (const shape of shapes) {
        const d = shape.getAttribute("d");
        if (d !== null) expect(d.trim(), `${name}: empty d`).not.toBe("");
        const r = shape.getAttribute("r");
        if (r !== null) expect(Number(r), `${name}: zero circle radius`).toBeGreaterThan(0);
        const rx = shape.getAttribute("rx");
        const ry = shape.getAttribute("ry");
        if (rx !== null && ry !== null) {
          expect(Number(rx), `${name}: zero ellipse rx`).toBeGreaterThan(0);
          expect(Number(ry), `${name}: zero ellipse ry`).toBeGreaterThan(0);
        }
      }
    }
  });

  it("keeps every glyph's ink inside the 2.35–13.65 envelope", () => {
    // Off-grid geometry passed every ban above, so this pass reads the
    // actual numbers: paths walked command by command (an arc's rotation,
    // flags and radii are parameters, not coordinates), circles and
    // ellipses as their full ink. Each value holds to the envelope the set
    // doc states — the bound a 1.5-wide stroke may not leave. A hair of
    // tolerance absorbs float jitter in the derived ink (centre ± radius),
    // not off-grid ink: real drift moves by tenths, not by 1e-9.
    for (const name of THE_SET) {
      const values = geometryValues(svgOf(name));
      expect(values.length, `${name}: scanned no geometry`).toBeGreaterThan(0);
      for (const value of values) {
        expect(value, `${name}: ink at ${value}`).toBeGreaterThanOrEqual(BOX_MIN - 1e-9);
        expect(value, `${name}: ink at ${value}`).toBeLessThanOrEqual(BOX_MAX + 1e-9);
      }
    }
  });
});
