// @vitest-environment node
/**
 * The wizard's search-param seam: the pure read/serialize pair and the genre
 * join rule the backend contract binds. These are the routing-param parser and
 * validator TESTING.md owes a unit test — the hook that drives them through a
 * real router is exercised in BasisStep.test.tsx.
 */
import { describe, expect, it } from "vitest";

import { demos } from "@shell/lib/generated/demos";

import {
  DEFAULT_TARGET_WORDS,
  GENRE_CAP,
  GENRE_PILLS,
  basisComplete,
  findDemo,
  joinGenres,
  readWizardState,
  wizardSearch,
  wouldOverflow,
  type WizardState,
} from "./wizardState";

function state(patch: Partial<WizardState> = {}): WizardState {
  return { ...readWizardState({}), ...patch };
}

describe("readWizardState", () => {
  it("answers an empty address with the honest defaults", () => {
    const s = readWizardState({});
    expect(s.title).toBe("");
    expect(s.genrePills).toEqual([]);
    expect(s.targetWords).toBe(DEFAULT_TARGET_WORDS);
    expect(s.typology).toBeNull();
    expect(s.form).toBeNull();
    expect(s.aiRole).toBeNull();
    expect(s.canon).toBeNull();
    expect(s.demo).toBeNull();
  });

  it("reads every answer back from the address", () => {
    const s = readWizardState({
      title: "Die Winterchronik",
      genres: "Mystery & Noir,Historischer Roman",
      words: "80000",
      typology: "plantser",
      form: "save-the-cat",
      role: "lektor",
      canon: "4",
      demo: demos[0].slug,
    });
    expect(s.title).toBe("Die Winterchronik");
    expect(s.genrePills).toEqual(["Mystery & Noir", "Historischer Roman"]);
    expect(s.targetWords).toBe(80000);
    expect(s.typology).toBe("plantser");
    expect(s.form).toBe("save-the-cat");
    expect(s.aiRole).toBe("lektor");
    expect(s.canon).toBe(4);
    expect(s.demo).toBe(demos[0].slug);
  });

  it("refuses unknown demos, genres, enums and out-of-range numbers", () => {
    const s = readWizardState({
      demo: "not-a-demo",
      genres: "Mystery & Noir,Lyrik,Mystery & Noir",
      words: "0",
      typology: "dreamer",
      form: "nine-act",
      role: "ghost",
      canon: "9",
    });
    expect(s.demo).toBeNull();
    // Lyrik is outside the five pills; the duplicate collapses.
    expect(s.genrePills).toEqual(["Mystery & Noir"]);
    expect(s.targetWords).toBe(DEFAULT_TARGET_WORDS);
    expect(s.typology).toBeNull();
    expect(s.form).toBeNull();
    expect(s.aiRole).toBeNull();
    expect(s.canon).toBeNull();
  });

  it("clamps the word target to the Integer column's own bounds", () => {
    expect(readWizardState({ words: "2147483648" }).targetWords).toBe(DEFAULT_TARGET_WORDS);
    expect(readWizardState({ words: "2147483647" }).targetWords).toBe(2147483647);
    expect(readWizardState({ words: "1" }).targetWords).toBe(1);
    expect(readWizardState({ words: "abc" }).targetWords).toBe(DEFAULT_TARGET_WORDS);
  });

  it("honors the genre cap even on a hand-edited address, in order", () => {
    // All five together run past the cap; the read keeps the leading prefix
    // that fits and drops the pill that would overflow.
    const s = readWizardState({ genres: GENRE_PILLS.join(",") });
    expect(joinGenres(s.genrePills).length).toBeLessThanOrEqual(GENRE_CAP);
    expect(s.genrePills).toEqual(GENRE_PILLS.slice(0, s.genrePills.length));
  });
});

describe("wizardSearch", () => {
  it("serializes a full state and drops the defaults", () => {
    const search = wizardSearch(
      state({
        title: "Dead Signal",
        genrePills: ["Mystery & Noir"],
        targetWords: 70000,
        typology: "plotter",
        form: "three-act",
        aiRole: "archivar",
        canon: 3,
        demo: demos[0].slug,
      }),
    );
    expect(search).toEqual({
      title: "Dead Signal",
      genres: "Mystery & Noir",
      words: 70000,
      typology: "plotter",
      form: "three-act",
      role: "archivar",
      canon: 3,
      demo: demos[0].slug,
    });
    // The default state leaves the address clean.
    expect(wizardSearch(state())).toEqual({
      title: undefined,
      genres: undefined,
      words: undefined,
      typology: undefined,
      form: undefined,
      role: undefined,
      canon: undefined,
      demo: undefined,
    });
  });

  it("round-trips through the read without loss", () => {
    const original = state({
      title: "  Im Stillen Wald  ",
      genrePills: ["Literarische Belletristik", "Historischer Roman"],
      targetWords: 55000,
      typology: "pantser",
      form: "heros-journey",
      aiRole: "sparring",
      canon: 5,
      demo: null,
    });
    const search = wizardSearch(original);
    const back = readWizardState(search as Record<string, unknown>);
    expect(back).toEqual(original);
  });

  it("clears a whitespace-only title instead of carrying it", () => {
    expect(wizardSearch(state({ title: "   " })).title).toBeUndefined();
  });
});

describe("the genre join rule", () => {
  it("joins the selected pills with ', ' into the one backend string", () => {
    expect(joinGenres(["Mystery & Noir", "Historischer Roman"])).toBe(
      "Mystery & Noir, Historischer Roman",
    );
    expect(joinGenres([])).toBe("");
  });

  it("blocks only the add that would overflow the 80-char cap", () => {
    // 29 + 25 + 2 = 56 fits; adding the 33-char Low Fantasy runs to 91.
    const two = ["Science Fiction & Speculative", "Literarische Belletristik"];
    expect(joinGenres(two).length).toBeLessThanOrEqual(GENRE_CAP);
    expect(wouldOverflow(two, "Low Fantasy / Magischer Realismus")).toBe(true);
    expect(wouldOverflow(two, "Mystery & Noir")).toBe(false);
    // Removing a selected pill is never an overflow.
    expect(wouldOverflow(two, "Science Fiction & Speculative")).toBe(false);
  });

  it("the three long pills fit the cap exactly at 80", () => {
    const three = ["Historischer Roman", "Literarische Belletristik", "Low Fantasy / Magischer Realismus"];
    expect(joinGenres(three).length).toBe(80);
    expect(wouldOverflow(three, "Mystery & Noir")).toBe(true);
  });
});

describe("basisComplete and findDemo", () => {
  it("is complete iff a demo is chosen or a title stands", () => {
    expect(basisComplete(state())).toBe(false);
    expect(basisComplete(state({ title: "   " }))).toBe(false);
    expect(basisComplete(state({ title: "Ein Titel" }))).toBe(true);
    expect(basisComplete(state({ demo: demos[0].slug }))).toBe(true);
  });

  it("finds the three real demos and refuses a stranger", () => {
    for (const demo of demos) {
      expect(findDemo(demo.slug)?.title).toBe(demo.title);
    }
    expect(findDemo("nope")).toBeNull();
    expect(findDemo(null)).toBeNull();
  });
});