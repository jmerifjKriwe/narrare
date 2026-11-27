// @vitest-environment node
/**
 * The manuscript's faces (design §6.5): the prose carries the manuscript's own
 * `lang`, and the shell answers with faces the reader's system cannot choose
 * for it. `web/globals.css` is read here the way `tokens.test.ts` reads it —
 * the text is the truth, no browser needed. Each `:lang()` rule repeats its
 * token's base stack first, then adds the language's Han families, then closes
 * with the base's generic family, so no generic family can sit ahead of a Han
 * family and swallow it (fontconfig resolves a generic against the system's
 * whole fallback list).
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const WEB = new URL("..", import.meta.url).pathname;
const CSS = readFileSync(join(WEB, "globals.css"), "utf8");

/** The Han families each manuscript language adds, in the rule's order. */
const HAN_FAMILIES: Record<"zh" | "ja" | "ko", { ui: string[]; serif: string[] }> = {
  zh: {
    ui: ['"PingFang SC"', '"Microsoft YaHei"', '"Noto Sans CJK SC"', '"Source Han Sans SC"'],
    serif: ['"Songti SC"', '"SimSun"', '"Noto Serif CJK SC"', '"Source Han Serif SC"'],
  },
  ja: {
    ui: ['"Hiragino Sans"', '"Yu Gothic"', '"Meiryo"', '"Noto Sans CJK JP"'],
    serif: ['"Yu Mincho"', '"Hiragino Mincho ProN"', '"Noto Serif CJK JP"'],
  },
  ko: {
    ui: ['"Apple SD Gothic Neo"', '"Malgun Gothic"', '"Noto Sans CJK KR"'],
    serif: ['"AppleMyungjo"', '"Batang"', '"Noto Serif CJK KR"'],
  },
};

/** Every Han family the three rules name, once. */
const EVERY_HAN_FAMILY = [
  ...new Set(Object.values(HAN_FAMILIES).flatMap((stacks) => [...stacks.ui, ...stacks.serif])),
];

/** The rule's normalized body, from its `:lang()` selector to its close. */
function ruleBlock(language: string): string {
  const start = CSS.indexOf(`:lang(${language}) {`);
  return CSS.slice(start, CSS.indexOf("}", start)).replace(/\s+/g, " ");
}

/** One declaration's value inside a rule block. */
function declaration(block: string, token: string): string {
  const start = block.indexOf(`${token}:`);
  return block.slice(start + token.length + 1, block.indexOf(";", start)).trim();
}

/** A value's families, in order. */
function families(value: string): string[] {
  return value.split(",").map((family) => family.trim());
}

describe("the manuscript's language faces", () => {
  it.each(["zh", "ja", "ko"] as const)("gives %s its own stacks", (language) => {
    const block = ruleBlock(language);
    expect(block).toContain("--font-ui:");
    expect(block).toContain("--font-serif:");
    expect(block).toContain(HAN_FAMILIES[language].ui.join(", "));
    expect(block).toContain(HAN_FAMILIES[language].serif.join(", "));
  });

  it("keeps the base stacks free of Han families", () => {
    const start = CSS.indexOf(":root {");
    const root = CSS.slice(start, CSS.indexOf("}", start));
    for (const family of EVERY_HAN_FAMILY) expect(root).not.toContain(family);
  });

  it.each(["zh", "ja", "ko"] as const)(
    "puts %s's generic family last, never before a Han family",
    (language) => {
      const block = ruleBlock(language);
      for (const [token, generic] of [
        ["--font-ui", "sans-serif"],
        ["--font-serif", "serif"],
      ] as const) {
        const value = declaration(block, token);
        const han = token === "--font-ui" ? HAN_FAMILIES[language].ui : HAN_FAMILIES[language].serif;
        // The base's generic family closes the declaration.
        expect(families(value).at(-1)).toBe(generic);
        // Neither generic name stands ahead of the rule's first Han family.
        const beforeHan = value.slice(0, value.indexOf(han[0]));
        expect(beforeHan).not.toContain("sans-serif");
        expect(beforeHan).not.toContain("serif");
      }
    },
  );
});
