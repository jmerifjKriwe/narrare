/**
 * The new-book dialog's pure model — the wizard step 1 seam shapes the
 * dialog re-owns (rule 1: a capability never imports another): the five
 * genre pills joined to the one ≤80-char string the backend binds, the
 * overflow refusal that disables a pill instead of dropping a choice, and
 * the draft's format bands over the word target. No React, no i18n runtime.
 */
import { describe, expect, it } from "vitest";

import {
  DEFAULT_TARGET_WORDS,
  GENRE_CAP,
  GENRE_PILLS,
  GENRE_PILL_DEFS,
  TARGET_WORDS_MAX,
  WORDS_MAX,
  WORDS_MIN,
  WORDS_PER_NORMSEITE,
  WORDS_STEP,
  joinGenres,
  wordBand,
  wouldOverflow,
} from "./newBook";

describe("the genre join — one string, the backend's cap", () => {
  it("joins the selected pills with ', ' in selection order", () => {
    expect(joinGenres([])).toBe("");
    expect(joinGenres(["Mystery & Noir"])).toBe("Mystery & Noir");
    expect(joinGenres(["Science Fiction & Speculative", "Mystery & Noir"])).toBe(
      "Science Fiction & Speculative, Mystery & Noir",
    );
  });

  it("carries exactly the five pills the draft draws, in its order", () => {
    expect(GENRE_PILL_DEFS.map((pill) => pill.value)).toEqual([
      "Science Fiction & Speculative",
      "Mystery & Noir",
      "Historischer Roman",
      "Literarische Belletristik",
      "Low Fantasy / Magischer Realismus",
    ]);
    expect(GENRE_PILLS).toEqual(GENRE_PILL_DEFS.map((pill) => pill.value));
    expect(GENRE_CAP).toBe(80);
  });

  it("the cap is the joined string's own length — 80 stands, 81 refuses", () => {
    const seventySeven = "a".repeat(77);
    expect(joinGenres([seventySeven, "b"]).length).toBe(80);
    expect(wouldOverflow([seventySeven], "b")).toBe(false);
    const seventyEight = "a".repeat(78);
    expect(joinGenres([seventyEight, "b"]).length).toBe(81);
    expect(wouldOverflow([seventyEight], "b")).toBe(true);
  });

  it("a selected pill is never an add — removing it is always allowed", () => {
    const full = ["Science Fiction & Speculative", "Mystery & Noir", "Historischer Roman"];
    expect(wouldOverflow(full, "Historischer Roman")).toBe(false);
    expect(wouldOverflow(full, "Literarische Belletristik")).toBe(true);
    expect(wouldOverflow(full, "Low Fantasy / Magischer Realismus")).toBe(true);
    // The draft's own three-pill selection: 65 chars, the fourth would be 92.
    expect(joinGenres(full).length).toBe(65);
    expect(joinGenres([...full, "Literarische Belletristik"]).length).toBe(92);
  });
});

describe("the word target — the draft's default and format bands", () => {
  it("defaults to 65.000 and keeps the Integer column's ceiling", () => {
    expect(DEFAULT_TARGET_WORDS).toBe(65_000);
    expect(TARGET_WORDS_MAX).toBe(2_147_483_647);
    expect(WORDS_PER_NORMSEITE).toBe(270);
  });

  it("the bands answer the draft's gauge boundaries, edge by edge", () => {
    expect(wordBand(1)).toBe("short");
    expect(wordBand(9_999)).toBe("short");
    expect(wordBand(10_000)).toBe("novella");
    expect(wordBand(49_999)).toBe("novella");
    expect(wordBand(50_000)).toBe("novel");
    expect(wordBand(65_000)).toBe("novel");
    expect(wordBand(99_999)).toBe("novel");
    expect(wordBand(100_000)).toBe("epic");
    expect(wordBand(TARGET_WORDS_MAX)).toBe("epic");
  });

  it("the Normseite figure is floored — 65.000 reads 240, never 241", () => {
    expect(Math.floor(DEFAULT_TARGET_WORDS / WORDS_PER_NORMSEITE)).toBe(240);
    expect(Math.floor(30_000 / WORDS_PER_NORMSEITE)).toBe(111);
  });

  it("the slider's range is the draft's own — 20k to 140k in 5k steps", () => {
    expect(WORDS_MIN).toBe(20_000);
    expect(WORDS_MAX).toBe(140_000);
    expect(WORDS_STEP).toBe(5_000);
    // The default sits on the slider's own grid, reachable by keyboard.
    expect(DEFAULT_TARGET_WORDS).toBeGreaterThanOrEqual(WORDS_MIN);
    expect(DEFAULT_TARGET_WORDS).toBeLessThanOrEqual(WORDS_MAX);
    expect((DEFAULT_TARGET_WORDS - WORDS_MIN) % WORDS_STEP).toBe(0);
  });
});
