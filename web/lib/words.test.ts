import { describe, expect, it } from "vitest";

import { countWords } from "./words";

/**
 * The client half of the shared word rule (R31): the server is the authority
 * and counts with one whitespace class — `\s` as the database's `[[:space:]]`
 * means it, plus the three near spaces a browser counts, and never U+FEFF,
 * which is a character, not a gap. The probes are the server tests' own four,
 * plus the FEFF line the JS `\s` would get wrong on its own.
 */
describe("countWords", () => {
  it("counts plain words", () => {
    expect(countWords("eins zwei drei")).toBe(3);
  });

  it("splits on the no-break space between words", () => {
    expect(countWords("eins\u00a0zwei")).toBe(2);
  });

  it("counts an ideographic-space-only body as nothing", () => {
    expect(countWords("\u3000")).toBe(0);
  });

  it("counts a figure-space-only body as nothing", () => {
    expect(countWords("\u2007")).toBe(0);
  });

  it("does not split on the zero-width no-break space", () => {
    // JavaScript's own `\s` class contains U+FEFF; the database's does not.
    // The shared rule follows the server: a FEFF joins, it never separates.
    expect(countWords("eins\uFEFFzwei")).toBe(1);
  });

  it("trims both ends, the way the server's one replace does", () => {
    // Without the global flag the one regex stops after its first match:
    // the leading run goes, the trailing one stays, and a padded body
    // counts a word that is not there.
    expect(countWords("  eins zwei  ")).toBe(2);
  });

  it("counts an empty body as nothing", () => {
    expect(countWords("")).toBe(0);
  });
});
