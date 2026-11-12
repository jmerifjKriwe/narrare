// @vitest-environment jsdom
/**
 * The cover's contract, pinned beside the other class helpers: the tone is
 * a pure hash of the title — deterministic, in range, spread across all
 * four tones — and the tile renders the 3:4 aspect, the exact tone classes
 * of the spec's quartet (pale, sepia, ink, slate — the last is O-2's
 * drafted ground), the spine strip every tone wears, sepia's gold frame,
 * pale's eyebrow, the serif lettering clamped to three lines, and the
 * aria-hidden that keeps the title out of the tree the card's link already
 * names (title and word count are the card's accessible name, not the
 * tile's — Task 10 pins that side). The frozen hash pins are the point:
 * the move from three tones to four re-buckets every book at once, so the
 * mapping must stay a reviewed decision.
 *
 * The forced-colors leg pins structure, not colour: the lettering is real
 * text and the decorative layers carry none, so a forced palette cannot
 * erase the title.
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Cover, coverTone, type CoverTone } from "./Cover";

const NAMES = ["pale", "sepia", "ink", "slate"] as const;
const GROUNDS = ["bg-cover-pale", "bg-cover-sepia", "bg-cover-ink", "bg-cover-slate"] as const;

/** Twenty hashed titles: enough that every tone is represented. */
const TITLES = Array.from({ length: 20 }, (_, index) => `Buch ${index}`);
const byTone = (tone: CoverTone) => TITLES.find((title) => coverTone(title) === tone)!;

afterEach(cleanup);

describe("coverTone", () => {
  it("is deterministic and lands inside the four tones", () => {
    const titles = [
      "Das Wattenmeer",
      "Der Sturm",
      "",
      "Übers Meer",
      "📚 Der Sturm — die zweite Auflage",
    ];
    for (const title of titles) {
      const tone = coverTone(title);
      expect([...NAMES], title).toContain(tone);
      expect(coverTone(title), title).toBe(tone);
    }
  });

  it("pins the tone of named titles", () => {
    // Frozen from the first green run of the four-tone hash. One value per
    // tone, so the pin itself cannot hide a collapsed hash. The quartet
    // re-bucketed every book against the old trio's pins — a reviewed
    // decision, not a drift.
    expect(coverTone("Das Wattenmeer")).toBe("slate");
    expect(coverTone("Das Zählwerk")).toBe("pale");
    expect(coverTone("")).toBe("sepia");
    expect(coverTone("Übers Meer")).toBe("ink");
  });

  it("wears the cover token of its tone, never an action or area token", () => {
    for (const tone of [0, 1, 2, 3] as const) {
      const { container } = render(<Cover title={byTone(NAMES[tone])} />);
      const tile = container.firstElementChild as HTMLElement;
      expect(tile.getAttribute("data-cover-tone")).toBe(NAMES[tone]);
      expect(tile.className).toContain(GROUNDS[tone]);
      expect(tile.className).not.toContain("bg-primary");
      expect(tile.className).not.toContain("bg-foreground");
      // The slate ground is its own token: the area hue paints accents, not
      // this object, even though the two share a value.
      expect(tile.className).not.toContain("bg-area-chat");
      cleanup();
    }
  });

  it("spreads the alphabet across all four tones", () => {
    const tones = new Set(
      "abcdefghijklmnopqrstuvwxyz"
        .split("")
        .map((letter) => coverTone(`Der ${letter}strom`)),
    );
    expect(tones.size).toBe(4);
  });
});

describe("Cover", () => {
  it("renders the 3:4 tile in the tone the title hashes to, hidden from the tree", () => {
    render(<Cover title="Das Wattenmeer" />);
    const tile = screen.getByText("Das Wattenmeer").parentElement as HTMLElement;
    expect(tile.className).toContain("aspect-[3/4]");
    expect(tile.className).toContain("bg-cover-slate");
    expect(tile.getAttribute("aria-hidden")).toBe("true");
  });

  it("wears the eyebrow's genre, or the language when there is none", () => {
    // Der Sturm lands on slate, one of the tones that set the eyebrow in
    // the top-left corner.
    const withGenre = render(<Cover title="Der Sturm" genre="Roman" language="de" />);
    expect(withGenre.getByText("Roman")).toBeTruthy();
    // One line, on the design's micro-label step: a long genre must not
    // wrap over the title below it.
    expect(withGenre.getByText("Roman").className).toContain("truncate");
    expect(withGenre.getByText("Roman").className).toContain("text-eyebrow");
    cleanup();
    const withoutGenre = render(<Cover title="Der Sturm" language="de" />);
    expect(withoutGenre.getByText("DE")).toBeTruthy();
    cleanup();
    const bare = render(<Cover title="Der Sturm" />);
    expect(bare.container.querySelector("[data-cover-eyebrow]")).toBeNull();
  });

  it("treats an empty genre as no genre", () => {
    const { getByText } = render(<Cover title="Der Sturm" genre="  " language="de" />);
    expect(getByText("DE")).toBeTruthy();
  });

  it("wears the spine strip on every tone, at the strength its ground names", () => {
    // The rendered composition names the strength per tone — pale 20 %,
    // sepia 40 %, slate 40 %, ink 60 %: the dark shelf names all four and
    // the light shelf agrees on pale. A strength that drifts from its
    // screen fails here; a uniform one is imperceptible on the midnight
    // ground.
    const strengths: Record<CoverTone, string> = {
      pale: "bg-black/20",
      sepia: "bg-black/40",
      ink: "bg-black/60",
      slate: "bg-black/40",
    };
    for (const name of NAMES) {
      const { container } = render(<Cover title={byTone(name)} />);
      const spine = container.querySelector("[data-cover-spine]") as HTMLElement;
      // 5 px of the ground darkened: the strip is not the tone's ink, which
      // would lighten the dark grounds it has to shade.
      expect(spine, name).toBeTruthy();
      expect(spine.className, name).toContain("w-[5px]");
      expect(spine.className, name).toContain("left-0");
      expect(spine.className, name).toContain(strengths[name]);
      expect(spine.className, name).not.toContain("bg-current");
      cleanup();
    }
  });

  it("draws its gold frame only on the sepia tone", () => {
    const sepia = render(<Cover title={byTone("sepia")} />);
    const frame = sepia.container.querySelector("[data-cover-frame]") as HTMLElement;
    expect(frame).not.toBeNull();
    // 1 px gold hairline at a 5 px offset: the tone's own ink washed over
    // the terracotta reads as the frame's warm gold.
    expect(frame.className).toContain("inset-[5px]");
    expect(frame.className).toContain("border-current");
    cleanup();
    for (const name of ["pale", "ink", "slate"] as const) {
      const other = render(<Cover title={byTone(name)} />);
      expect(other.container.querySelector("[data-cover-frame]"), name).toBeNull();
      cleanup();
    }
  });

  it("centres the ink tone's title with its metadata at 60% opacity", () => {
    const { container, getByText } = render(<Cover title="Übers Meer" genre="Roman" />);
    // Übers Meer lands on ink: the one tone whose composition centres.
    expect(coverTone("Übers Meer")).toBe("ink");
    expect(getByText("Übers Meer").className).toContain("text-center");
    const metadata = container.querySelector("[data-cover-eyebrow]") as HTMLElement;
    expect(metadata).not.toBeNull();
    expect(metadata.className).toContain("opacity-60");
    expect(metadata.className).toContain("text-center");
    // The caption follows the centred title instead of taking the corner
    // the other tones give it: it is not an absolutely placed layer.
    expect(metadata.className).not.toContain("absolute");
  });

  it("clamps the lettering to three lines with the overflow the clamp carries", () => {
    const longTitle = "Der Sturm über das Wattenmeer der Halligen".repeat(3);
    render(<Cover title={longTitle} />);
    const lettering = screen.getByText(longTitle);
    expect(lettering.className).toContain("line-clamp-3");
    expect(lettering.className).toContain("overflow-hidden");
    // The brand serif, 600: the cover's title is a heading, and the serif's
    // headings carry the wordmark's weight.
    expect(lettering.className).toContain("font-semibold");
    expect(lettering.className).toContain("[font-family:'EB_Garamond',Georgia,'Times_New_Roman',serif]");
  });

  it("keeps the title readable by structure, not colour", () => {
    // Forced colours strip the palette; the lettering survives because it
    // is real text and nothing decorative is woven through it. The spine,
    // the frame and the eyebrow are their own elements and carry no text.
    const { container } = render(<Cover title={byTone("sepia")} genre="Roman" />);
    for (const decorative of ["[data-cover-spine]", "[data-cover-frame]"]) {
      const layer = container.querySelector(decorative) as HTMLElement;
      expect(layer.textContent).toBe("");
    }
    const lettering = screen.getByText(byTone("sepia"));
    expect(lettering.textContent).toBe(byTone("sepia"));
    // The title is not a child of any decorative layer: it keeps its own
    // place in the tile whatever a forced palette paints.
    for (const decorative of ["[data-cover-spine]", "[data-cover-frame]"]) {
      expect(lettering.closest(decorative)).toBeNull();
    }
  });

  it("sizes the hero's cover wider than the shelf card's", () => {
    // The drafted shelf's own widths (screens/library/shelf.html): the
    // card's cover at w-36, the hero's at w-48 — the tile's height always
    // deriving from the 3:4 norm, never from a drafted h-* pair.
    render(<Cover title="Der Sturm" size="hero" />);
    const heroTile = screen.getByText("Der Sturm").parentElement as HTMLElement;
    expect(heroTile.className).toContain("w-48");
    render(<Cover title="Winterhaus" size="card" />);
    const cardTile = screen.getByText("Winterhaus").parentElement as HTMLElement;
    expect(cardTile.className).toContain("w-36");
    expect(cardTile.className).not.toContain("w-20");
    expect(heroTile.className).not.toContain("w-36");
  });
});
