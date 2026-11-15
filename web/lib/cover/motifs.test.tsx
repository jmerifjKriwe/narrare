// @vitest-environment jsdom
/**
 * The eight genre vignettes are the cover's only imagery: one hairline SVG
 * per channel, ported from the Stitch spec's Sektion 02. The contract is
 * presentation, not behavior — every channel answers with its own
 * svg[data-channel], the eight shapes stay pairwise distinct (no genre
 * borrows another's motif), and each vignette wears the hairline grammar:
 * fill none, stroke currentColor so the ink token drives it, a 1.2 stroke,
 * the 48×48 viewBox, and aria-hidden so the decoration never reaches a
 * screen reader. No hardcoded pigment may sit inside a motif.
 */
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { CoverChannel } from "./cover";
import { GenreMotif } from "./motifs";

const CHANNELS: CoverChannel[] = [
  "scifi",
  "fantasy",
  "mystery",
  "literary",
  "historical",
  "romance",
  "thriller",
  "fallback",
];

afterEach(() => {
  cleanup();
});

describe("GenreMotif", () => {
  it("renders an svg[data-channel] for every channel", () => {
    for (const channel of CHANNELS) {
      const { container, unmount } = render(<GenreMotif channel={channel} />);
      expect(container.querySelector(`svg[data-channel="${channel}"]`)).not.toBeNull();
      unmount();
    }
  });

  it("gives the eight channels eight distinct shapes", () => {
    const shapes = new Set<string>();
    for (const channel of CHANNELS) {
      const { container, unmount } = render(<GenreMotif channel={channel} />);
      const svg = container.querySelector(`svg[data-channel="${channel}"]`);
      // The inner markup is the shape: the root's data-channel attribute
      // would make two identical motifs compare distinct.
      shapes.add(svg?.innerHTML ?? "");
      unmount();
    }
    expect(shapes.size).toBe(8);
  });

  it("wears the hairline grammar and stays decorative", () => {
    for (const channel of CHANNELS) {
      const { container, unmount } = render(<GenreMotif channel={channel} />);
      const svg = container.querySelector(`svg[data-channel="${channel}"]`);
      expect(svg?.getAttribute("viewBox")).toBe("0 0 48 48");
      expect(svg?.getAttribute("fill")).toBe("none");
      expect(svg?.getAttribute("stroke")).toBe("currentColor");
      expect(svg?.getAttribute("aria-hidden")).toBe("true");
      expect(Number(svg?.getAttribute("stroke-width"))).toBeCloseTo(1.2, 5);
      // The ink token is the only pigment: no hex, no rgb() inside a motif.
      expect(svg?.innerHTML).not.toMatch(/#[0-9a-f]{3,8}\b|rgb\(/i);
      unmount();
    }
  });

  it("hands the caller's className to the svg", () => {
    const { container } = render(<GenreMotif channel="scifi" className="size-10 opacity-35" />);
    const svg = container.querySelector('svg[data-channel="scifi"]');
    expect(svg?.getAttribute("class")).toBe("size-10 opacity-35");
  });
});
