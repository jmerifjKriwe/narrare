// @vitest-environment jsdom
/**
 * The book object as the wizard and the shelf will wear it: a deterministic,
 * presentational cover ported from the Stitch cover-system spec. The contract
 * here is presentation and robustness, not behavior — the model (cover.ts)
 * already pins the mapping, the variant axis and the edges; this file pins
 * what the component does with them.
 *
 * The rulings it obeys: ground/ink ride LITERAL Tailwind utilities (R2 — no
 * dynamic concatenation, no inline var(), because Tailwind v4 only emits the
 * classes it sees verbatim); the three variants are three real compositions,
 * not one layout with a different attribute (R10, spec Sektion 03); dark mode
 * keeps the pigment and adds only the uniform white-8% rim and the deeper
 * contact shadow (R9, spec Sektion 06). The edges (Sektion 05) must never break
 * the layout: a long title clamps to three lines without an ellipsis and lets
 * the vignette recede, an absent author keeps a localized line, an unknown
 * genre falls to the neutral linen with the atelier seal, and the miniatur
 * keeps only the monogram inside its 36×48 box.
 *
 * The locale is pinned to German (the du-tone catalog) and reset after each
 * test, so the assertions read the words the app actually speaks.
 */
import { act, cleanup, render, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { applyLocale } from "../locale";
import { BookCover } from "./BookCover";
import { COVER_SIZES, coverModel, variantFor, type CoverChannel, type CoverSize } from "./cover";

/** The spec's own Fall A title: 75 code points, eleven words. */
const LONG_TITLE =
  "Die Chroniken von Svalbard und das verschollene Signal im subglazialen Riss";
/** A single 63-code-point word: shortTitle AND longTitle at once. */
const MAMMOTH_WORD = "Rindfleischetikettierungsüberwachungsaufgabenübertragungsgesetz";

/** Three titles the hash spreads over the three axes, all in one genre. */
const VARIANT_TITLES: Record<0 | 1 | 2, string> = {
  0: "Singularität Eins",
  1: "Villa Blackwood",
  2: "Frequenz Null",
};

function root(container: HTMLElement): HTMLElement {
  return container.firstElementChild as HTMLElement;
}

beforeEach(() => {
  applyLocale("de");
});

afterEach(() => {
  cleanup();
  applyLocale("en");
});

describe("BookCover anatomy", () => {
  it("renders the title, the localized genre eyebrow and the author", () => {
    const { container, getByText } = render(
      <BookCover title="Am Flussufer" genre="Literary" author="C. V. H." size="wizard" />,
    );
    expect(root(container).textContent).toContain("Am Flussufer");
    expect(getByText("Literarischer Roman")).toBeTruthy();
    expect(getByText("C. V. H.")).toBeTruthy();
    // Literary rides the legacy sepia ground, via literal utilities (R2).
    expect(root(container).classList.contains("bg-cover-sepia")).toBe(true);
    expect(root(container).classList.contains("text-cover-sepia-ink")).toBe(true);
  });

  it("sizes the root from COVER_SIZES for every canonical view", () => {
    for (const size of Object.keys(COVER_SIZES) as CoverSize[]) {
      const { container, unmount } = render(<BookCover title="Dead Signal" size={size} />);
      expect(root(container).style.width).toBe(`${COVER_SIZES[size].width}px`);
      expect(root(container).style.height).toBe(`${COVER_SIZES[size].height}px`);
      unmount();
    }
  });

  it("wears the asymmetric rounding, the dark rim and the tactile shadow", () => {
    const { container } = render(<BookCover title="Dead Signal" size="wizard" />);
    const cls = root(container).className;
    expect(root(container).classList.contains("rounded-l-none")).toBe(true);
    expect(root(container).classList.contains("rounded-r-[6px]")).toBe(true);
    // The uniform 1px rim on three sides (R9): never the spine side.
    for (const side of ["border-t", "border-r", "border-b"]) {
      expect(root(container).classList.contains(side)).toBe(true);
    }
    expect(root(container).classList.contains("border-l")).toBe(false);
    // white/8 in the dark half, transparent in the light one — the app's
    // color-scheme mechanism, not a media query that a forced theme outruns.
    expect(cls).toContain("[border-color:light-dark(transparent,rgba(255,255,255,0.08))]");
    // Both tactile shadows ported verbatim, switched by light-dark(). The
    // arbitrary-property form is deliberate: shadow-[light-dark(...)] would be
    // misread as a shadow *color*, since light-dark() is a color function.
    expect(cls).toContain("[box-shadow:light-dark(");
    expect(cls).toContain("rgba(44,24,16,0.06)");
    expect(cls).toContain("rgba(0,0,0,0.6)");
    expect(cls).toContain("rgba(0,0,0,0.45)");
  });

  it("scales the right radius with the book (R13, Sektion 04); the spine stays square", () => {
    const radii: Record<CoverSize, string> = {
      wizard: "rounded-r-[6px]", // spec 701
      hero: "rounded-r-[5px]", // spec 724
      shelf: "rounded-r-[4px]", // spec 747
      mini: "rounded-r-[2px]", // spec 764
    };
    for (const size of Object.keys(radii) as CoverSize[]) {
      const { container, unmount } = render(<BookCover title="Dead Signal" size={size} />);
      const el = root(container);
      expect(el.classList.contains("rounded-l-none")).toBe(true);
      expect(el.classList.contains(radii[size])).toBe(true);
      // The radius scales with the book, it is not fixed: no other size's
      // radius leaks onto this root.
      for (const [other, radius] of Object.entries(radii)) {
        if (other !== size) expect(el.classList.contains(radius)).toBe(false);
      }
      unmount();
    }
  });

  it("ports the spine crease: pale grounds the pale crease, dark grounds the black", () => {
    const cases: Array<[string, string]> = [
      ["Mystery", "rgba(44,24,16,0.2)"], // pale ground → pale crease
      ["Lyrik", "rgba(44,24,16,0.2)"], // fallback linen → pale crease
      ["Literary", "rgba(0,0,0,0.28)"], // sepia → black crease
      ["Science Fiction", "rgba(0,0,0,0.28)"], // ink → black crease
    ];
    for (const [genre, marker] of cases) {
      const { container, unmount } = render(
        <BookCover title="Dead Signal" genre={genre} size="wizard" />,
      );
      const crease = root(container).querySelector(".inset-y-0");
      expect(crease).not.toBeNull();
      expect(crease?.className).toContain(marker);
      expect(crease?.classList.contains("w-3")).toBe(true); // wizard, spec Sektion 04
      unmount();
    }
  });

  it("keeps the blind-deboss boundary on full sizes and culls it at mini", () => {
    const full = render(<BookCover title="Dead Signal" size="wizard" />);
    const deboss = root(full.container).querySelector(".inset-\\[6px\\]");
    expect(deboss).not.toBeNull();
    expect(deboss?.classList.contains("rounded-r-[4px]")).toBe(true);
    expect(deboss?.classList.contains("border-amber-300/20")).toBe(true);
    full.unmount();

    const mini = render(<BookCover title="Dead Signal" size="mini" />);
    expect(root(mini.container).querySelector(".inset-\\[6px\\]")).toBeNull();
  });
});

describe("BookCover per-size matrix (Sektion 04)", () => {
  it("sets the eyebrow type per size (R14): wizard 9px, hero 8px, shelf 7px", () => {
    const types: Record<"wizard" | "hero" | "shelf", [string, string]> = {
      wizard: ["text-[9px]", "tracking-widest"], // spec 704
      hero: ["text-[8px]", "tracking-widest"], // spec 727
      shelf: ["text-[7px]", "tracking-wider"], // spec 750
    };
    for (const size of Object.keys(types) as Array<"wizard" | "hero" | "shelf">) {
      const { container, unmount } = render(
        <BookCover title="Dead Signal" genre="Historical" size={size} />,
      );
      const eyebrow = within(container).getByText("Historischer Roman");
      expect(eyebrow.classList.contains(types[size][0])).toBe(true);
      expect(eyebrow.classList.contains(types[size][1])).toBe(true);
      // No other size's type leaks onto this eyebrow.
      for (const [other, [fontSize]] of Object.entries(types)) {
        if (other !== size) expect(eyebrow.classList.contains(fontSize)).toBe(false);
      }
      // The anatomy specimen's old 10px/0.2em baseline is not the matrix.
      expect(eyebrow.classList.contains("text-[10px]")).toBe(false);
      expect(eyebrow.classList.contains("tracking-[0.2em]")).toBe(false);
      unmount();
    }
  });

  it("sets the normal title's leading per size: shelf snug, wizard and hero tight", () => {
    const leadings: Record<"wizard" | "hero" | "shelf", [string, string]> = {
      wizard: ["leading-tight", "max-h-[3.75em]"], // spec 713
      hero: ["leading-tight", "max-h-[3.75em]"], // spec 736
      shelf: ["leading-snug", "max-h-[4.125em]"], // spec 753
    };
    for (const size of Object.keys(leadings) as Array<"wizard" | "hero" | "shelf">) {
      const { container, unmount } = render(<BookCover title="Dead Signal" size={size} />);
      const title = within(container).getByText("Dead Signal");
      expect(title.classList.contains(leadings[size][0])).toBe(true);
      // The three-line clamp tracks the leading (3 × the line-height).
      expect(title.classList.contains(leadings[size][1])).toBe(true);
      const other = leadings[size][0] === "leading-tight" ? "leading-snug" : "leading-tight";
      expect(title.classList.contains(other)).toBe(false);
      unmount();
    }
  });

  it("spaces the title block per size: wizard space-y-1, hero and shelf space-y-0.5", () => {
    const spacing: Record<"wizard" | "hero" | "shelf", string> = {
      wizard: "space-y-1", // spec 712
      hero: "space-y-0.5", // spec 735
      shelf: "space-y-0.5", // spec 752
    };
    for (const size of Object.keys(spacing) as Array<"wizard" | "hero" | "shelf">) {
      // Variants 0 and 1 both carry a title+author block; the hash is
      // size-independent, so these two titles hit both at every size.
      for (const variant of [0, 1] as const) {
        const title = VARIANT_TITLES[variant];
        const { container, unmount } = render(
          <BookCover title={title} genre="Science Fiction" size={size} />,
        );
        const block = within(container).getByText(title).parentElement;
        expect(block?.classList.contains(spacing[size])).toBe(true);
        const other = spacing[size] === "space-y-1" ? "space-y-0.5" : "space-y-1";
        expect(block?.classList.contains(other)).toBe(false);
        unmount();
      }
    }
  });

  it("scales the spine crease with the book (R12); no other size's width leaks", () => {
    const widths: Record<CoverSize, string> = {
      wizard: "w-3", // spec 702
      hero: "w-2.5", // spec 725
      shelf: "w-2", // spec 748
      mini: "w-1", // spec 765
    };
    for (const size of Object.keys(widths) as CoverSize[]) {
      const { container, unmount } = render(<BookCover title="Dead Signal" size={size} />);
      const crease = root(container).querySelector(".inset-y-0");
      expect(crease).not.toBeNull();
      expect(crease?.classList.contains(widths[size])).toBe(true);
      for (const [other, width] of Object.entries(widths)) {
        if (other !== size) expect(crease?.classList.contains(width)).toBe(false);
      }
      unmount();
    }
  });
});

describe("BookCover ground and ink (R2)", () => {
  it("applies a literal bg-cover-* / text-cover-*-ink pair for every channel", () => {
    const pairs: Array<[CoverChannel, string, string, string]> = [
      ["scifi", "Science Fiction", "bg-cover-ink", "text-cover-ink-ink"],
      ["fantasy", "Fantasy", "bg-cover-fantasy", "text-cover-fantasy-ink"],
      ["mystery", "Mystery", "bg-cover-pale", "text-cover-pale-ink"],
      ["literary", "Literary", "bg-cover-sepia", "text-cover-sepia-ink"],
      ["historical", "Historical", "bg-cover-slate", "text-cover-slate-ink"],
      ["romance", "Romance", "bg-cover-romance", "text-cover-romance-ink"],
      ["thriller", "Thriller", "bg-cover-thriller", "text-cover-thriller-ink"],
      ["fallback", "Lyrik", "bg-cover-fallback", "text-cover-fallback-ink"],
    ];
    for (const [channel, genre, ground, ink] of pairs) {
      const { container, unmount } = render(
        <BookCover title="Dead Signal" genre={genre} size="wizard" />,
      );
      const el = root(container);
      expect(el.getAttribute("data-channel")).toBe(channel);
      expect(el.classList.contains(ground)).toBe(true);
      expect(el.classList.contains(ink)).toBe(true);
      // No dynamic pigment: the scanner must see the class, not a var().
      expect(el.className).not.toContain("bg-[var(");
      expect(el.className).not.toContain("text-[var(");
      unmount();
    }
  });

  it("pins the literal palette to the model's groundToken/inkToken for all eight channels", () => {
    const genres: Record<CoverChannel, string> = {
      scifi: "Science Fiction",
      fantasy: "Fantasy",
      mystery: "Mystery",
      literary: "Literary",
      historical: "Historical",
      romance: "Romance",
      thriller: "Thriller",
      fallback: "Lyrik",
    };
    for (const channel of Object.keys(genres) as CoverChannel[]) {
      const genre = genres[channel];
      const model = coverModel({ title: "Dead Signal", genre, size: "wizard" });
      expect(model.channel).toBe(channel);
      const { container, unmount } = render(
        <BookCover title="Dead Signal" genre={genre} size="wizard" />,
      );
      const el = root(container);
      // The expected classes are computed from the model's tokens here in
      // the test; the component itself keeps literals (R2). Exactly one
      // ground and one ink class, and they are the model's — so the static
      // PALETTE cannot silently drift from CHANNEL_TOKENS.
      const grounds = Array.from(el.classList).filter((cls) => cls.startsWith("bg-cover-"));
      const inks = Array.from(el.classList).filter((cls) => cls.startsWith("text-cover-"));
      expect(grounds).toEqual([`bg-${model.groundToken}`]);
      expect(inks).toEqual([`text-${model.inkToken}`]);
      unmount();
    }
  });
});

describe("BookCover size tiers", () => {
  it("mini keeps only the monogram inside the 36×48 box", () => {
    const { container, getByText, queryByText } = render(
      <BookCover title="Dead Signal" genre="Science Fiction" author="K. V. Holm" size="mini" />,
    );
    const monogram = getByText("DS");
    // The miniature's monogram is bold (spec 767), not semibold.
    expect(monogram.classList.contains("font-bold")).toBe(true);
    expect(monogram.classList.contains("font-semibold")).toBe(false);
    expect(queryByText("Dead Signal")).toBeNull();
    expect(queryByText("K. V. Holm")).toBeNull();
    expect(queryByText("Science Fiction")).toBeNull();
    expect(container.querySelector("svg[data-channel]")).toBeNull();
    expect(root(container).style.width).toBe("36px");
    expect(root(container).style.height).toBe("48px");
  });

  it("falls back to N for an empty title's monogram", () => {
    const { getByText } = render(<BookCover title="   " size="mini" />);
    expect(getByText("N")).toBeTruthy();
  });

  it("shows the eyebrow and author exactly when the model's tier flags say so", () => {
    for (const size of Object.keys(COVER_SIZES) as CoverSize[]) {
      const props = { title: "Dead Signal", genre: "Science Fiction", author: "K. V. Holm" };
      const model = coverModel({ ...props, size });
      const { container, unmount } = render(<BookCover {...props} size={size} />);
      const view = within(container);
      expect(view.queryByText("Science Fiction") !== null).toBe(model.showEyebrow);
      expect(view.queryByText("K. V. Holm") !== null).toBe(model.showAuthor);
      unmount();
    }
  });

  it("wizard and hero keep the vignette; shelf culls it", () => {
    const shelf = render(<BookCover title="Dead Signal" genre="Science Fiction" size="shelf" />);
    expect(
      coverModel({ title: "Dead Signal", genre: "Science Fiction", size: "shelf" }).showVignette,
    ).toBe(false);
    expect(shelf.container.querySelector("svg[data-channel]")).toBeNull();
    shelf.unmount();

    const hero = render(<BookCover title="Dead Signal" genre="Science Fiction" size="hero" />);
    expect(
      coverModel({ title: "Dead Signal", genre: "Science Fiction", size: "hero" }).showVignette,
    ).toBe(true);
    expect(hero.container.querySelector('svg[data-channel="scifi"]')).not.toBeNull();
    hero.unmount();

    const wizard = render(<BookCover title="Dead Signal" genre="Science Fiction" size="wizard" />);
    expect(wizard.container.querySelector('svg[data-channel="scifi"]')).not.toBeNull();
  });
});

describe("BookCover edges (spec Sektion 05)", () => {
  it("clamps a long title to three lines without an ellipsis; the vignette recedes", () => {
    const { container, getByText } = render(
      <BookCover title={LONG_TITLE} genre="Thriller" author="Prof. L. Nansen" size="wizard" />,
    );
    const title = getByText(LONG_TITLE);
    expect(title.classList.contains("overflow-hidden")).toBe(true);
    expect(title.classList.contains("max-h-[4.125em]")).toBe(true);
    expect(title.classList.contains("leading-snug")).toBe(true);
    expect(title.textContent).not.toContain("…");
    expect(root(container).textContent).not.toContain("…");
    // The vector steps back when the title runs long.
    expect(container.querySelector("svg[data-channel]")).toBeNull();
  });

  it("survives a single mammoth word: clamped, broken, never overflowing", () => {
    const { container, getByText } = render(
      <BookCover title={MAMMOTH_WORD} genre="Fantasy" size="wizard" />,
    );
    const title = getByText(MAMMOTH_WORD);
    expect(title.classList.contains("overflow-hidden")).toBe(true);
    expect(title.classList.contains("break-words")).toBe(true);
    expect(title.classList.contains("max-h-[4.125em]")).toBe(true);
    expect(title.textContent).not.toContain("…");
    expect(container.querySelector("svg[data-channel]")).toBeNull();
  });

  it("gives a one-word title the larger monumental scale", () => {
    const short = render(<BookCover title="Echo" genre="Fantasy" size="wizard" />);
    const shortTitle = short.getByText("Echo");
    expect(shortTitle.classList.contains("text-[28px]")).toBe(true);
    expect(shortTitle.classList.contains("leading-none")).toBe(true);
    expect(shortTitle.classList.contains("tracking-wide")).toBe(true);
    short.unmount();

    const normal = render(<BookCover title="Dead Signal" genre="Fantasy" size="wizard" />);
    expect(normal.getByText("Dead Signal").classList.contains("text-[21px]")).toBe(true);
  });

  it("shows the localized Anonymus for a null, empty or whitespace author", () => {
    for (const author of [null, "", "   "]) {
      const { getByText, unmount } = render(
        <BookCover title="Fragment III" genre="Literary" author={author} size="wizard" />,
      );
      expect(getByText("Anonymus")).toBeTruthy();
      unmount();
    }
  });

  it("falls back to the neutral linen and the atelier seal for an unknown genre", () => {
    for (const genre of ["Lyrik", null, "", "Essayistik", "unknown"]) {
      const { container, unmount } = render(
        <BookCover title="Unbenannter Entwurf" genre={genre} size="wizard" />,
      );
      const el = root(container);
      expect(el.getAttribute("data-channel")).toBe("fallback");
      expect(el.classList.contains("bg-cover-fallback")).toBe(true);
      expect(container.querySelector('svg[data-channel="fallback"]')).not.toBeNull();
      unmount();
    }
  });
});

describe("BookCover variant axis (R10, spec Sektion 03)", () => {
  it("is deterministic: the same props carry the same data-variant in {0,1,2}", () => {
    const a = render(<BookCover title="Dead Signal" genre="Science Fiction" size="wizard" />);
    const b = render(<BookCover title="Dead Signal" genre="Science Fiction" size="wizard" />);
    const va = root(a.container).getAttribute("data-variant");
    const vb = root(b.container).getAttribute("data-variant");
    expect(va).toBe(vb);
    expect(["0", "1", "2"]).toContain(va);
    expect(va).toBe(String(variantFor("Dead Signal")));
  });

  it("does not force two same-genre titles onto one axis", () => {
    const a = render(<BookCover title={VARIANT_TITLES[0]} genre="Science Fiction" size="wizard" />);
    const b = render(<BookCover title={VARIANT_TITLES[1]} genre="Science Fiction" size="wizard" />);
    expect(root(a.container).getAttribute("data-variant")).not.toBe(
      root(b.container).getAttribute("data-variant"),
    );
  });

  it("builds three structurally distinct compositions, not one layout relabeled", () => {
    const views = ([0, 1, 2] as const).map((variant) => {
      const view = render(
        <BookCover title={VARIANT_TITLES[variant]} genre="Science Fiction" size="wizard" />,
      );
      const el = root(view.container);
      expect(el.getAttribute("data-variant")).toBe(String(variant));
      return { variant, el, view };
    });

    const [v0, v1, v2] = views;

    // 0 — centered classic: the title block centers, the vignette rests in the
    // optical middle on a centered band.
    const title0 = within(v0.el).getByText(VARIANT_TITLES[0]);
    expect(title0.parentElement?.classList.contains("text-center")).toBe(true);
    const svg0 = v0.el.querySelector("svg[data-channel]");
    expect(svg0?.parentElement?.classList.contains("justify-center")).toBe(true);

    // 1 — offset axis: the vignette shifts off the spine on a pl-8 band, the
    // title block stays left-aligned (no centering).
    const title1 = within(v1.el).getByText(VARIANT_TITLES[1]);
    expect(title1.parentElement?.classList.contains("text-center")).toBe(false);
    const svg1 = v1.el.querySelector("svg[data-channel]");
    expect(svg1?.parentElement?.classList.contains("pl-8")).toBe(true);

    // 2 — monumental whitespace: the vignette is a small edge mark beside the
    // eyebrow in the top row, the title owns a my-auto band, the author sits
    // under a rule at the foot.
    const title2 = within(v2.el).getByText(VARIANT_TITLES[2]);
    expect(title2.parentElement?.classList.contains("my-auto")).toBe(true);
    const svg2 = v2.el.querySelector("svg[data-channel]");
    const topRow = svg2?.parentElement;
    expect(topRow?.classList.contains("justify-between")).toBe(true);
    expect(topRow?.textContent).toContain("Science Fiction");
    const author2 = within(v2.el).getByText("Anonymus");
    expect(author2.classList.contains("border-t")).toBe(true);

    // The three compositions are pairwise different markup even with the
    // title text AND the data-variant attribute masked out — the difference
    // is the layout itself, not the words and not the label.
    const shape = (el: HTMLElement) =>
      el.innerHTML.replace(/data-variant="\d"/g, "").replace(/>[^<]+</g, "><");
    const shapes = new Set(views.map(({ el }) => shape(el)));
    expect(shapes.size).toBe(3);

    for (const { view } of views) view.unmount();
  });
});

describe("BookCover i18n", () => {
  it("speaks the active locale and re-renders when it changes", () => {
    const { getByText, queryByText } = render(
      <BookCover title="Fragment III" genre="Literary" author={null} size="wizard" />,
    );
    expect(getByText("Literarischer Roman")).toBeTruthy();
    expect(getByText("Anonymus")).toBeTruthy();

    act(() => {
      applyLocale("en");
    });
    expect(queryByText("Literarischer Roman")).toBeNull();
    expect(getByText("Literary Fiction")).toBeTruthy();
    expect(getByText("Anonymous")).toBeTruthy();

    act(() => {
      applyLocale("fr");
    });
    expect(getByText("Roman littéraire")).toBeTruthy();
    expect(getByText("Anonyme")).toBeTruthy();
  });
});
