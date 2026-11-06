// @vitest-environment jsdom
/**
 * The cover's contract, pinned beside the other class helpers: the tone is
 * a pure hash of the title — deterministic, in range, spread across all
 * three tones — and the tile renders the 3:4 aspect, the exact tone classes
 * of the spec's trio (pale, sepia, ink — R32), the serif lettering clamped
 * to three lines with hidden overflow, and the aria-hidden that keeps the
 * title out of the tree the card's link already names. The frozen hash pins
 * survived the round-1 re-table (R32 moved the tones, not the hash, so
 * every book's tone index is what it was); a hash change would shift every
 * cover at once and must stay a reviewed decision.
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Cover, coverTone } from "./Cover";

afterEach(cleanup);

describe("coverTone", () => {
  it("is deterministic and lands inside the three tones", () => {
    const titles = [
      "Das Wattenmeer",
      "Der Sturm",
      "",
      "Übers Meer",
      "📚 Der Sturm — die zweite Auflage",
    ];
    for (const title of titles) {
      const tone = coverTone(title);
      expect([0, 1, 2], title).toContain(tone);
      expect(coverTone(title), title).toBe(tone);
    }
  });

  it("pins the tone of named titles", () => {
    // Frozen from the first green run with FNV-1a; unchanged by the round-1
    // re-table, which moved the tones, not the hash. One value per tone, so
    // the pin itself cannot hide a collapsed hash.
    expect(coverTone("Das Wattenmeer")).toBe(2);
    expect(coverTone("Das Zählwerk")).toBe(0);
    expect(coverTone("")).toBe(1);
  });

  it("wears the cover token of its tone, never an action token", () => {
    const titles = Array.from({ length: 20 }, (_, index) => `Buch ${index}`);
    const byTone = (tone: number) => titles.find((title) => coverTone(title) === tone)!;
    const names = ["pale", "sepia", "ink"] as const;
    const grounds = ["bg-cover-pale", "bg-cover-sepia", "bg-cover-ink"] as const;
    for (const tone of [0, 1, 2] as const) {
      const { container } = render(<Cover title={byTone(tone)} />);
      const tile = container.firstElementChild as HTMLElement;
      expect(tile.getAttribute("data-cover-tone")).toBe(names[tone]);
      expect(tile.className).toContain(grounds[tone]);
      expect(tile.className).not.toContain("bg-primary");
      expect(tile.className).not.toContain("bg-foreground");
      cleanup();
    }
  });

  it("spreads the alphabet across all three tones", () => {
    const tones = new Set(
      "abcdefghijklmnopqrstuvwxyz"
        .split("")
        .map((letter) => coverTone(`Der ${letter}strom`)),
    );
    expect(tones.size).toBe(3);
  });
});

describe("Cover", () => {
  it("renders the 3:4 tile in the tone the title hashes to, hidden from the tree", () => {
    render(<Cover title="Das Wattenmeer" />);
    const tile = screen.getByText("Das Wattenmeer").parentElement as HTMLElement;
    expect(tile.className).toContain("aspect-[3/4]");
    expect(tile.className).toContain("bg-cover-ink");
    expect(tile.getAttribute("aria-hidden")).toBe("true");
  });

  it("wears the eyebrow's genre, or the language when there is none", () => {
    const withGenre = render(<Cover title="Der Sturm" genre="Roman" language="de" />);
    expect(withGenre.getByText("Roman")).toBeTruthy();
    cleanup();
    const withoutGenre = render(<Cover title="Der Sturm" language="de" />);
    expect(withoutGenre.getByText("DE")).toBeTruthy();
    cleanup();
    const bare = render(<Cover title="Der Sturm" />);
    expect(bare.container.querySelector("[data-cover-eyebrow]")).toBeNull();
  });

  it("draws its frame only on the sepia tone", () => {
    const titles = Array.from({ length: 20 }, (_, index) => `Buch ${index}`);
    const byTone = (tone: number) => titles.find((title) => coverTone(title) === tone)!;
    const sepia = render(<Cover title={byTone(1)} />);
    expect(sepia.container.querySelector("[data-cover-frame]")).not.toBeNull();
    cleanup();
    const pale = render(<Cover title={byTone(0)} />);
    expect(pale.container.querySelector("[data-cover-frame]")).toBeNull();
  });

  it("clamps the lettering to three lines with the overflow the clamp carries", () => {
    const longTitle = "Der Sturm über das Wattenmeer der Halligen".repeat(3);
    render(<Cover title={longTitle} />);
    const lettering = screen.getByText(longTitle);
    expect(lettering.className).toContain("line-clamp-3");
    expect(lettering.className).toContain("overflow-hidden");
    expect(lettering.className).toContain("[font-family:'EB_Garamond',Georgia,'Times_New_Roman',serif]");
  });

  it("sizes the hero's cover wider than the shelf card's", () => {
    render(<Cover title="Der Sturm" size="lg" />);
    const tile = screen.getByText("Der Sturm").parentElement as HTMLElement;
    expect(tile.className).toContain("w-28");
    expect(tile.className).not.toContain("w-20");
  });
});
