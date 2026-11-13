// @vitest-environment jsdom
/**
 * The cover's contract, pinned beside the other class helpers: the tone is
 * a pure hash of the title — deterministic, in range, spread across all
 * four tones — and the tile renders the drafted composition in the exact
 * tone classes of the spec's quartet (pale, sepia, ink, slate — the last is
 * O-2's drafted ground): the 3:4-ish geometry of the screens, the spine
 * gradient every tone wears, the top block (eyebrow + italic serif title at
 * the prose-heading step), the middle genre motif, the author foot, sepia's
 * gold frame, and the hero's imprint row with its corner motif. The
 * aria-hidden keeps the title out of the tree the card's link already names
 * (title and word count are the card's accessible name, not the tile's —
 * Task 10 pins that side). The frozen hash pins are the point: the move
 * from three tones to four re-buckets every book at once, so the mapping
 * must stay a reviewed decision.
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

/** The tile that holds a rendered title. */
function tileOf(container: HTMLElement): HTMLElement {
  return container.firstElementChild as HTMLElement;
}

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
      const tile = tileOf(container);
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
  it("renders the tile in the tone the title hashes to, hidden from the tree", () => {
    const { container } = render(<Cover title="Das Wattenmeer" />);
    const tile = screen.getByText("Das Wattenmeer").closest("[data-cover-tone]") as HTMLElement;
    expect(tileOf(container)).toBe(tile);
    expect(tile.className).toContain("bg-cover-slate");
    expect(tile.getAttribute("aria-hidden")).toBe("true");
  });

  it("sizes the grid and hero covers to the drafted geometry", () => {
    // The screens' own boxes (shelf.html): the grid cover 36 × 52, the hero
    // 48 × 72. The shelf card's cover is not a 3:4 box any more — the screen
    // draws a taller card tile, and the screen wins (§5.4).
    const card = render(<Cover title="Winterhaus" size="card" />);
    const cardTile = tileOf(card.container);
    expect(cardTile.className).toContain("w-36");
    expect(cardTile.className).toContain("h-52");
    cleanup();
    const hero = render(<Cover title="Der Sturm" size="hero" />);
    const heroTile = tileOf(hero.container);
    expect(heroTile.className).toContain("w-48");
    expect(heroTile.className).toContain("h-72");
    expect(heroTile.className).not.toContain("w-36");
  });

  it("composes every tone the same way: top title, middle motif, author foot", () => {
    // The screen's one composition replaces the old bottom-aligned and
    // centred variants: a cover reads top to bottom on every ground.
    for (const name of NAMES) {
      const { container } = render(
        <Cover title={byTone(name)} size="card" genre="Sci-Fi" author="Calder" />,
      );
      const tile = tileOf(container);
      const eyebrow = tile.querySelector("[data-cover-eyebrow]") as HTMLElement;
      const title = tile.querySelector("[data-cover-title]") as HTMLElement;
      const motif = tile.querySelector("[data-cover-motif]") as HTMLElement;
      const author = tile.querySelector("[data-cover-author]") as HTMLElement;
      expect(eyebrow, name).not.toBeNull();
      expect(title, name).not.toBeNull();
      expect(motif, name).not.toBeNull();
      expect(author, name).not.toBeNull();
      // Reading order: the eyebrow and title at the top, the glyph in the
      // middle, the author at the foot.
      const html = tile.innerHTML;
      expect(html.indexOf("data-cover-eyebrow"), name).toBeLessThan(
        html.indexOf("data-cover-motif"),
      );
      expect(html.indexOf("data-cover-motif"), name).toBeLessThan(
        html.indexOf("data-cover-author"),
      );
      // One composition for all tones: no ground centres or bottom-aligns.
      expect(title.className, name).not.toContain("text-center");
      expect(tile.className, name).toContain("justify-between");
      cleanup();
    }
  });

  it("sets the title at the drafted step per size", () => {
    // The grid's prose-heading-2 (21 / 28) and the hero's prose-heading-1
    // (26 / 34), in the brand serif's italic 600.
    const card = render(<Cover title="Winterhaus" size="card" />);
    const cardTitle = card.container.querySelector("[data-cover-title]") as HTMLElement;
    expect(cardTitle.className).toContain("text-[1.3125rem]");
    expect(cardTitle.className).toContain("leading-[1.75rem]");
    expect(cardTitle.className).toContain("font-garamond");
    expect(cardTitle.className).toContain("italic");
    expect(cardTitle.className).toContain("font-semibold");
    cleanup();
    const hero = render(<Cover title="Der Sturm" size="hero" />);
    const heroTitle = hero.container.querySelector("[data-cover-title]") as HTMLElement;
    expect(heroTitle.className).toContain("text-[1.625rem]");
    expect(heroTitle.className).toContain("leading-[2.125rem]");
  });

  it("wears the eyebrow's genre, or the language when there is none", () => {
    // Der Sturm lands on slate, one of the tones that set the eyebrow at
    // the top of the tile.
    const withGenre = render(<Cover title="Der Sturm" size="card" genre="Roman" language="de" />);
    expect(withGenre.getByText("Roman")).toBeTruthy();
    // One line, on the design's micro-label step: a long genre must not
    // wrap over the title below it.
    expect(withGenre.getByText("Roman").className).toContain("truncate");
    expect(withGenre.getByText("Roman").className).toContain("text-eyebrow");
    cleanup();
    const withoutGenre = render(<Cover title="Der Sturm" size="card" language="de" />);
    expect(withoutGenre.getByText("DE")).toBeTruthy();
    cleanup();
    const bare = render(<Cover title="Der Sturm" size="card" />);
    expect(bare.container.querySelector("[data-cover-eyebrow]")).toBeNull();
  });

  it("treats an empty genre as no genre", () => {
    const { getByText } = render(<Cover title="Der Sturm" size="card" genre="  " language="de" />);
    expect(getByText("DE")).toBeTruthy();
  });

  it("draws the motif each genre names, and the neutral ring when it knows none", () => {
    const cases: [string | null, string][] = [
      ["Sci-Fi", "target"],
      ["Science Fiction", "target"],
      ["Mystery", "house"],
      ["Krimi", "house"],
      ["Lit Fiction", "waves"],
      ["Literatur", "waves"],
      ["Historisch", "foggy"],
      ["Historischer Roman", "foggy"],
      ["Sachbuch", "ring"],
      [null, "ring"],
    ];
    for (const [genre, motif] of cases) {
      const { container } = render(<Cover title="Der Sturm" size="card" genre={genre} />);
      const glyph = container.querySelector("[data-cover-motif]") as HTMLElement;
      expect(glyph.getAttribute("data-cover-motif"), String(genre)).toBe(motif);
      cleanup();
    }
  });

  it("keeps the motif in the tone's accent ink", () => {
    // The three dark grounds wear the drafted amber (`--cover-motif`, 4.61:1
    // on sepia light through 9.53:1 on ink dark); pale keeps its own deep
    // ink, where amber cannot clear 3:1 on the linen (13.48:1 / 12.44:1).
    const pale = render(<Cover title={byTone("pale")} size="card" />);
    expect(
      (pale.container.querySelector("[data-cover-motif]") as HTMLElement).className,
    ).toContain("text-cover-pale-ink");
    cleanup();
    for (const name of ["sepia", "ink", "slate"] as const) {
      const { container } = render(<Cover title={byTone(name)} size="card" />);
      expect(
        (container.querySelector("[data-cover-motif]") as HTMLElement).className,
        name,
      ).toContain("text-cover-motif");
      cleanup();
    }
  });

  it("puts the author at the foot, writing — when the book has none", () => {
    const known = render(<Cover title="Der Sturm" size="card" author="Calder" />);
    expect(
      (known.container.querySelector("[data-cover-author]") as HTMLElement).textContent,
    ).toBe("Calder");
    cleanup();
    const unknown = render(<Cover title="Der Sturm" size="card" author={null} />);
    // The book has no author yet: the drafted line holds its place with the
    // placeholder, never an invented name. Real data, no follow-up issue.
    expect(
      (unknown.container.querySelector("[data-cover-author]") as HTMLElement).textContent,
    ).toBe("—");
    cleanup();
    const absent = render(<Cover title="Der Sturm" size="card" />);
    expect(absent.container.querySelector("[data-cover-author]")).toBeNull();
  });

  it("renders the hero's imprint row only when the prop is present", () => {
    const withImprint = render(
      <Cover title="Übers Meer" size="hero" imprint="Atelier Opus IV" />,
    );
    const row = withImprint.container.querySelector("[data-cover-imprint]") as HTMLElement;
    expect(row).not.toBeNull();
    expect(row.textContent).toContain("Atelier Opus IV");
    cleanup();
    // Interim: no imprint field exists yet; the drafted slot holds its
    // place with the neutral value until one does (#832).
    const unknown = render(<Cover title="Übers Meer" size="hero" imprint={null} />);
    const unknownRow = unknown.container.querySelector("[data-cover-imprint]") as HTMLElement;
    expect(unknownRow).not.toBeNull();
    expect(unknownRow.textContent).toContain("—");
    cleanup();
    const absent = render(<Cover title="Übers Meer" size="hero" />);
    expect(absent.container.querySelector("[data-cover-imprint]")).toBeNull();
    cleanup();
    // The grid cover has no imprint row, even if a caller passes one: the
    // draft draws it on the hero only.
    const card = render(<Cover title="Winterhaus" size="card" imprint="Atelier Opus IV" />);
    expect(card.container.querySelector("[data-cover-imprint]")).toBeNull();
  });

  it("draws the hero's corner motif as decoration beside the imprint", () => {
    const { container } = render(
      <Cover title="Übers Meer" size="hero" imprint="Atelier Opus IV" />,
    );
    const corner = container.querySelector("[data-cover-corner]") as HTMLElement;
    expect(corner).not.toBeNull();
    expect(corner.getAttribute("aria-hidden")).toBe("true");
    expect(corner.querySelector("svg")).not.toBeNull();
    cleanup();
    const card = render(<Cover title="Winterhaus" size="card" />);
    expect(card.container.querySelector("[data-cover-corner]")).toBeNull();
  });

  it("adds the amber rule under the hero's eyebrow, and only there", () => {
    const hero = render(<Cover title="Übers Meer" size="hero" />);
    const rule = hero.container.querySelector("[data-cover-rule]") as HTMLElement;
    expect(rule).not.toBeNull();
    expect(rule.className).toContain("w-6");
    expect(rule.className).toContain("h-0.5");
    // Übers Meer lands on ink: the amber accent of the dark grounds.
    expect(rule.className).toContain("bg-cover-motif");
    cleanup();
    const card = render(<Cover title="Winterhaus" size="card" />);
    expect(card.container.querySelector("[data-cover-rule]")).toBeNull();
  });

  it("wears the spine gradient on every tone, at the drafted strength and width", () => {
    // The screens draw the spine as a 2.5-unit gradient on the grid cover
    // and 3.5 on the hero; the strength is the tone's own, because a
    // uniform one disappears on the midnight ground.
    const starts: Record<CoverTone, string> = {
      pale: "from-black/20",
      sepia: "from-black/35",
      ink: "from-black/50",
      slate: "from-black/40",
    };
    for (const name of NAMES) {
      const { container } = render(<Cover title={byTone(name)} size="card" />);
      const spine = container.querySelector("[data-cover-spine]") as HTMLElement;
      expect(spine, name).not.toBeNull();
      expect(spine.className, name).toContain("w-2.5");
      expect(spine.className, name).toContain("left-0");
      expect(spine.className, name).toContain("bg-gradient-to-r");
      expect(spine.className, name).toContain("to-transparent");
      expect(spine.className, name).toContain(starts[name]);
      cleanup();
    }
    const hero = render(<Cover title="Der Sturm" size="hero" />);
    const heroSpine = hero.container.querySelector("[data-cover-spine]") as HTMLElement;
    expect(heroSpine.className).toContain("w-3.5");
  });

  it("draws its gold frame only on the sepia tone", () => {
    const sepia = render(<Cover title={byTone("sepia")} size="card" />);
    const frame = sepia.container.querySelector("[data-cover-frame]") as HTMLElement;
    expect(frame).not.toBeNull();
    // 1 px gold hairline at a 5 px offset: the tone's own ink washed over
    // the terracotta reads as the frame's warm gold.
    expect(frame.className).toContain("inset-[5px]");
    expect(frame.className).toContain("border-current");
    cleanup();
    for (const name of ["pale", "ink", "slate"] as const) {
      const other = render(<Cover title={byTone(name)} size="card" />);
      expect(other.container.querySelector("[data-cover-frame]"), name).toBeNull();
      cleanup();
    }
  });

  it("clamps the title and truncates the author", () => {
    const longTitle = "Der Sturm über das Wattenmeer der Halligen".repeat(3);
    const { container } = render(
      <Cover title={longTitle} size="card" author={"Ein sehr langer Autorenname, der nicht passt"} />,
    );
    const title = container.querySelector("[data-cover-title]") as HTMLElement;
    expect(title.textContent).toBe(longTitle);
    expect(title.className).toContain("line-clamp-3");
    expect(title.className).toContain("overflow-hidden");
    const author = container.querySelector("[data-cover-author]") as HTMLElement;
    expect(author.className).toContain("truncate");
  });

  it("keeps the title readable by structure, not colour", () => {
    // Forced colours strip the palette; the lettering survives because it
    // is real text and nothing decorative is woven through it. The spine,
    // frame, motif and corner mark are their own elements and carry no
    // text.
    const { container } = render(
      <Cover title={byTone("sepia")} size="hero" genre="Roman" imprint="Atelier Opus IV" />,
    );
    for (const decorative of [
      "[data-cover-spine]",
      "[data-cover-frame]",
      "[data-cover-motif]",
      "[data-cover-corner]",
      "[data-cover-rule]",
    ]) {
      const layer = container.querySelector(decorative) as HTMLElement;
      expect(layer, decorative).not.toBeNull();
      expect(layer.textContent, decorative).toBe("");
    }
    const lettering = container.querySelector("[data-cover-title]") as HTMLElement;
    expect(lettering.textContent).toBe(byTone("sepia"));
    for (const decorative of ["[data-cover-spine]", "[data-cover-frame]"]) {
      expect(lettering.closest(decorative)).toBeNull();
    }
  });
});
