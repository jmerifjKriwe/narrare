// @vitest-environment jsdom
/**
 * The icon set's contract, pinned as records rather than single samples:
 * `icons` carries exactly the sixteen names (the wave's whole vocabulary
 * — a name that drifts in or out breaks a P9 consumer), and every one of
 * them renders through `Icon` as the same hidden 16×16 svg — stroked in
 * the ink around it, filled with nothing, sized by `size` alone. The
 * drawings themselves are geometry: a glyph that renders no shape, or
 * draws its metaphor as text, cannot do its job at 16 px.
 */
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Icon, icons, type IconName } from "./icons";

/** The sixteen names, verbatim: the set is exactly this and no more. */
const SIXTEEN = [
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

afterEach(cleanup);

describe("icons", () => {
  it("carries exactly the sixteen names of the set, verbatim", () => {
    expect(Object.keys(icons).sort()).toEqual([...SIXTEEN].sort());
  });

  it("renders every name as the same hidden 16×16 stroked svg", () => {
    expect(Object.fromEntries(SIXTEEN.map((name) => [name, contractOf(name)]))).toEqual(
      Object.fromEntries(SIXTEEN.map((name) => [name, SVG_CONTRACT])),
    );
  });

  it("scales width and height with size, together — the grid never stretches", () => {
    expect(contractOf("search", 20)).toEqual({ ...SVG_CONTRACT, width: "20", height: "20" });
  });

  it("draws every glyph as geometry, never as text or a fill", () => {
    // Shape first: a glyph with no drawing element renders as empty space.
    expect(
      SIXTEEN.filter(
        (name) =>
          svgOf(name).querySelector(
            "path, circle, ellipse, line, polyline, polygon, rect",
          ) === null,
      ),
    ).toEqual([]);
    // Then the bans: no glyph may write its metaphor, and any fill there is must be none.
    expect(SIXTEEN.filter((name) => svgOf(name).querySelector("text") !== null)).toEqual([]);
    expect(
      SIXTEEN.filter((name) =>
        [...svgOf(name).querySelectorAll("[fill]")].some(
          (element) => element.getAttribute("fill") !== "none",
        ),
      ),
    ).toEqual([]);
  });

  it("keeps all sixteen drawings distinct — cross dismisses, close folds a panel", () => {
    // cross and close must never converge on the same ✕: a dismissal drops
    // content, a close folds a panel away — and no two names may share a drawing.
    expect(new Set(SIXTEEN.map((name) => JSON.stringify(icons[name]))).size).toBe(16);
    expect(icons.close).not.toEqual(icons.cross);
  });
});
