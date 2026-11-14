// @vitest-environment node
import { describe, expect, it } from "vitest";
import {
  COVER_SIZES,
  channelFor,
  coverModel,
  variantFor,
  type CoverChannel,
  type CoverSize,
} from "./cover";
import { murmur3_32 } from "./hash";

describe("COVER_SIZES", () => {
  it("pins the four canonical view sizes", () => {
    expect(COVER_SIZES).toEqual({
      wizard: { width: 224, height: 300 },
      hero: { width: 192, height: 264 },
      shelf: { width: 144, height: 200 },
      mini: { width: 36, height: 48 },
    });
  });
});

describe("channelFor", () => {
  it("maps the canonical genre labels to their channels", () => {
    expect(channelFor("Science Fiction")).toBe("scifi");
    expect(channelFor("Fantasy")).toBe("fantasy");
    expect(channelFor("Mystery")).toBe("mystery");
    expect(channelFor("Literary")).toBe("literary");
    expect(channelFor("Historical")).toBe("historical");
    expect(channelFor("Romance")).toBe("romance");
    expect(channelFor("Thriller")).toBe("thriller");
  });
  it("normalizes case and surrounding whitespace", () => {
    expect(channelFor("SCIENCE FICTION")).toBe("scifi");
    expect(channelFor("  fantasy  ")).toBe("fantasy");
    expect(channelFor("MyStErY")).toBe("mystery");
  });
  it("knows the English and German aliases", () => {
    expect(channelFor("Sci-Fi")).toBe("scifi");
    expect(channelFor("literary fiction")).toBe("literary");
    expect(channelFor("Historischer Roman")).toBe("historical");
    expect(channelFor("Literarische Belletristik")).toBe("literary");
    expect(channelFor("Krimi")).toBe("mystery");
    expect(channelFor("Liebesroman")).toBe("romance");
  });
  it("falls back for absent, empty and unknown genres", () => {
    // Lyrik and Essayistik sit deliberately outside the genre matrix.
    for (const genre of [null, undefined, "", "   ", "Lyrik", "Essayistik", "unknown"]) {
      expect(channelFor(genre)).toBe("fallback");
    }
  });
});

describe("variantFor", () => {
  const titles = ["Dead Signal", "Echo", "Im Stillen Wald", "", "x".repeat(200)];
  it("is the title hash modulo three", () => {
    for (const title of titles) {
      expect(variantFor(title)).toBe(murmur3_32(title) % 3);
    }
  });
  it("is stable across calls and stays in {0, 1, 2}", () => {
    for (const title of titles) {
      const variant = variantFor(title);
      expect(variantFor(title)).toBe(variant);
      expect([0, 1, 2]).toContain(variant);
    }
  });
});

describe("coverModel", () => {
  function atSize(size: CoverSize) {
    return coverModel({
      title: "Dead Signal",
      genre: "Science Fiction",
      author: "K. V. Holm",
      size,
    });
  }

  it("builds the wizard model for a known genre", () => {
    expect(atSize("wizard")).toEqual({
      channel: "scifi",
      variant: (murmur3_32("Dead Signal") % 3) as 0 | 1 | 2,
      groundToken: "cover-ink",
      inkToken: "cover-ink-ink",
      width: 224,
      height: 300,
      showEyebrow: true,
      showAuthor: true,
      showVignette: true,
      monogram: false,
      monogramText: "DS",
      authorName: "K. V. Holm",
      anonymous: false,
      longTitle: false,
      shortTitle: false,
    });
  });

  it("keeps the vignette at hero and culls it at shelf", () => {
    expect(atSize("hero").showVignette).toBe(true);
    const shelf = atSize("shelf");
    expect(shelf.showVignette).toBe(false);
    expect(shelf.showEyebrow).toBe(true);
    expect(shelf.showAuthor).toBe(true);
    expect(shelf.monogram).toBe(false);
  });

  it("reduces mini to the monogram", () => {
    const mini = atSize("mini");
    expect(mini.monogram).toBe(true);
    expect(mini.showEyebrow).toBe(false);
    expect(mini.showAuthor).toBe(false);
    expect(mini.showVignette).toBe(false);
    expect(mini.width).toBe(36);
    expect(mini.height).toBe(48);
  });

  it("maps every channel to its ground and ink token", () => {
    const pairs: Record<CoverChannel, { genre: string; ground: string; ink: string }> = {
      scifi: { genre: "Science Fiction", ground: "cover-ink", ink: "cover-ink-ink" },
      fantasy: { genre: "Fantasy", ground: "cover-fantasy", ink: "cover-fantasy-ink" },
      mystery: { genre: "Mystery", ground: "cover-pale", ink: "cover-pale-ink" },
      literary: { genre: "Literary", ground: "cover-sepia", ink: "cover-sepia-ink" },
      historical: { genre: "Historical", ground: "cover-slate", ink: "cover-slate-ink" },
      romance: { genre: "Romance", ground: "cover-romance", ink: "cover-romance-ink" },
      thriller: { genre: "Thriller", ground: "cover-thriller", ink: "cover-thriller-ink" },
      fallback: { genre: "Lyrik", ground: "cover-fallback", ink: "cover-fallback-ink" },
    };
    for (const [channel, { genre, ground, ink }] of Object.entries(pairs)) {
      const model = coverModel({ title: "Dead Signal", genre, size: "wizard" });
      expect(model.channel).toBe(channel);
      expect(model.groundToken).toBe(ground);
      expect(model.inkToken).toBe(ink);
    }
  });

  it("falls back when the genre is absent", () => {
    const model = coverModel({ title: "Dead Signal", size: "wizard" });
    expect(model.channel).toBe("fallback");
    expect(model.groundToken).toBe("cover-fallback");
    expect(model.inkToken).toBe("cover-fallback-ink");
  });

  it("flags a long title and lets the vignette recede", () => {
    const model = coverModel({ title: "x".repeat(70), genre: "Fantasy", size: "wizard" });
    expect(model.longTitle).toBe(true);
    expect(model.showVignette).toBe(false);
    expect(coverModel({ title: "x".repeat(70), size: "hero" }).showVignette).toBe(false);
  });

  it("draws the long-title line strictly above sixty trimmed characters", () => {
    expect(coverModel({ title: "x".repeat(60), size: "wizard" }).longTitle).toBe(false);
    expect(coverModel({ title: "x".repeat(61), size: "wizard" }).longTitle).toBe(true);
    expect(coverModel({ title: `  ${"x".repeat(60)}  `, size: "wizard" }).longTitle).toBe(false);
  });

  it("counts code points, not UTF-16 units, at the long-title boundary", () => {
    // 31 astral glyphs + 29 spaces = 60 code points but 91 UTF-16 units:
    // the spec counts Zeichen, so the vignette must stay.
    const astral = "🚀 ".repeat(29) + "🚀🚀";
    expect([...astral]).toHaveLength(60);
    expect(astral.length).toBe(91);
    const model = coverModel({ title: astral, size: "wizard" });
    expect(model.longTitle).toBe(false);
    expect(model.showVignette).toBe(true);
    expect(coverModel({ title: astral, size: "hero" }).showVignette).toBe(true);
    // 61 code points is long even though every glyph is a single Zeichen.
    const longAstral = "🚀 ".repeat(30) + "🚀";
    expect([...longAstral]).toHaveLength(61);
    const long = coverModel({ title: longAstral, size: "wizard" });
    expect(long.longTitle).toBe(true);
    expect(long.showVignette).toBe(false);
  });

  it("treats a missing or whitespace author as anonymous", () => {
    for (const author of [null, undefined, "", "   "]) {
      const model = coverModel({ title: "Dead Signal", author, size: "wizard" });
      expect(model.anonymous).toBe(true);
      expect(model.authorName).toBe("");
      // The author line stays; the component localizes the placeholder.
      expect(model.showAuthor).toBe(true);
    }
  });

  it("trims the author name", () => {
    const model = coverModel({ title: "Dead Signal", author: "  K. V. Holm  ", size: "wizard" });
    expect(model.authorName).toBe("K. V. Holm");
    expect(model.anonymous).toBe(false);
  });

  it("marks a one-word title short, never a two-word one", () => {
    expect(coverModel({ title: "Echo", size: "wizard" }).shortTitle).toBe(true);
    expect(coverModel({ title: "  Echo  ", size: "wizard" }).shortTitle).toBe(true);
    expect(coverModel({ title: "Dead Signal", size: "wizard" }).shortTitle).toBe(false);
    expect(coverModel({ title: "", size: "wizard" }).shortTitle).toBe(false);
    expect(coverModel({ title: "   ", size: "wizard" }).shortTitle).toBe(false);
  });

  it("counts words, not characters, for the short title", () => {
    // A single mammoth word is short and long at once: the axes are independent.
    const mammoth = coverModel({ title: "x".repeat(70), size: "wizard" });
    expect(mammoth.shortTitle).toBe(true);
    expect(mammoth.longTitle).toBe(true);
  });

  it("builds the mini monogram from the first two title words", () => {
    expect(coverModel({ title: "Dead Signal", size: "mini" }).monogramText).toBe("DS");
    expect(coverModel({ title: "Echo", size: "mini" }).monogramText).toBe("E");
    expect(coverModel({ title: "Im Stillen Wald", size: "mini" }).monogramText).toBe("IS");
    expect(coverModel({ title: "Ähre im Wind", size: "mini" }).monogramText).toBe("ÄI");
    expect(coverModel({ title: "", size: "mini" }).monogramText).toBe("N");
    expect(coverModel({ title: "   ", size: "mini" }).monogramText).toBe("N");
  });

  it("uppercases each word before taking its first code point", () => {
    // "ß".toUpperCase() is "SS": uppercasing the initial alone would grow
    // the monogram to three letters. Each initial stays one code point.
    expect(coverModel({ title: "ßeta Wald", size: "mini" }).monogramText).toBe("SW");
    expect(coverModel({ title: "ßeta", size: "mini" }).monogramText).toBe("S");
  });

  it("is deterministic for the same input", () => {
    const input = {
      title: "Dead Signal",
      genre: "Science Fiction",
      author: "K. V. Holm",
      size: "wizard",
    } as const;
    expect(coverModel(input)).toEqual(coverModel(input));
  });

  it("hashes the trimmed title, so padding cannot shift the variant", () => {
    const padded = coverModel({ title: "  Dead Signal  ", size: "wizard" });
    expect(padded.variant).toBe(variantFor("Dead Signal"));
  });
});
