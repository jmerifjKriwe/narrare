// @vitest-environment node
/**
 * The scale's gate. The census in spec §11 is a command a human runs; this is
 * the same measurement in the suite, so a `text-lg` cannot ride in unnoticed
 * (#544, #573). Only `className="…"` literals are read — the shape §11
 * measures; `className={…}` templates are outside it on purpose.
 *
 * The steps themselves are measured against the design's table (spec §6.3):
 * the size, the leading each token carries, the weight and the tracking where
 * the norm names one — the prose's two chapter headings with them.
 */
import { readFileSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, relative } from "node:path";
import { compile } from "tailwindcss";
import { describe, expect, it } from "vitest";

const WEB = new URL("..", import.meta.url).pathname;
const REPO = new URL("../..", import.meta.url).pathname;
const resolveModule = createRequire(import.meta.url);
const STYLESHEET = readFileSync(join(WEB, "globals.css"), "utf8");
/**
 * The stylesheet without its comments — the rules and the tokens, nothing
 * else. A comment only when it opens a line: the `@source` path carries a
 * `/*` of its own, inside a string.
 */
const CSS = STYLESHEET.replace(/^\s*\/\*[\s\S]*?\*\//gm, "");
const TEXT_FAMILY = new Set([
  "left", "center", "right", "justify", "start", "end", "wrap", "nowrap",
  "balance", "pretty", "ellipsis", "clip", "inherit", "current", "transparent",
]);

const COLOUR_NAMES = new Set(
  [...CSS.matchAll(/--color-([a-z][a-z0-9-]*):/g)].map((m) => m[1]),
);
function isAllowedTextUtility(utility: string): boolean {
  const match = /^text-(.+)$/.exec(utility);
  if (!match) return true;
  const name = match[1];
  if (name.startsWith("[")) return true; // arbitrary value
  if (SCALE_STEPS.has(name)) return true;
  if (TEXT_FAMILY.has(name)) return true;
  if (COLOUR_NAMES.has(name)) return true;
  return false;
}
const CLASS = /className="([^"]*)"/g;

/**
 * The scale's steps, as the design names them (spec §6.3): the size in rem,
 * the leading as the ratio its token states, the weight every step carries,
 * and the tracking where the norm names one. The eyebrow is the design's
 * micro-label — 11 px on 16 px, weight 600, tracked 0.08 em; its uppercase
 * rides with the usage, because Tailwind's theme namespace carries no
 * text-transform.
 */
const SCALE: Record<string, { size: string; leading: string; weight: string; tracking?: string }> = {
  eyebrow: { size: "0.6875rem", leading: "1.45", weight: "600", tracking: "0.08em" },
  meta: { size: "0.75rem", leading: "1.42", weight: "400" },
  label: { size: "0.8125rem", leading: "1.38", weight: "500" },
  body: { size: "0.875rem", leading: "1.57", weight: "400" },
  emph: { size: "0.9375rem", leading: "1.47", weight: "600" },
  title: { size: "1.25rem", leading: "1.3", weight: "600" },
  hero: { size: "1.875rem", leading: "1.2", weight: "700", tracking: "-0.025em" },
};
const SCALE_STEPS = new Set(Object.keys(SCALE));

/** A token's value in the stylesheet. */
function token(name: string): string | null {
  return new RegExp(`--${name}:\\s*([^;]+);`).exec(CSS)?.[1].trim() ?? null;
}

/**
 * The declarations of one rule, found by its exact selector list — the
 * stylesheet's own text, so a rule that moves is still the rule that is read.
 */
function rule(...selectors: string[]): Record<string, string> {
  return declarationsIn(CSS, selectors);
}

/**
 * The declarations of one rule inside the utilities layer. The layer's own
 * braces wrap its rules, so the flat matcher above would read the layer's
 * opener as the rule's selector; this reads the layer's body instead.
 */
function utilitiesRule(...selectors: string[]): Record<string, string> {
  const open = CSS.indexOf("@layer utilities");
  if (open === -1) throw new Error("globals.css has no utilities layer");
  const body = CSS.slice(CSS.indexOf("{", open) + 1, CSS.lastIndexOf("}"));
  return declarationsIn(body, selectors);
}

/** The shared matcher behind `rule` and `utilitiesRule`. */
function declarationsIn(
  text: string,
  selectors: string[],
): Record<string, string> {
  for (const match of text.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const found = match[1].split(",").map((part) => part.trim().replace(/\s+/g, " "));
    if (found.length !== selectors.length) continue;
    if (!selectors.every((selector, at) => found[at] === selector)) continue;
    const declarations: Record<string, string> = {};
    for (const declaration of match[2].matchAll(/([\w-]+):\s*([^;]+);/g)) {
      declarations[declaration[1]] = declaration[2].replace(/\s+/g, " ").trim();
    }
    return declarations;
  }
  throw new Error(`globals.css has no rule for ${selectors.join(", ")}`);
}

/**
 * The stylesheet as Tailwind compiles it: the tokens' own utilities, so a step
 * the design names is checked where it is used. Compiled once, on demand.
 */
let compiled: Promise<string> | null = null;
function compileCss(): Promise<string> {
  compiled ??= compile(STYLESHEET, {
    base: WEB,
    loadStylesheet: async (id: string) => {
      const path = resolveModule.resolve(`${id}/index.css`);
      return { path, base: dirname(path), content: readFileSync(path, "utf8") };
    },
  }).then((compiler) =>
    compiler.build([
      "text-eyebrow",
      "text-meta",
      "text-label",
      "text-body",
      "text-emph",
      "text-title",
      "text-hero",
      "font-medium",
      "font-semibold",
      "tabular-nums",
      "uppercase",
    ]),
  );
  return compiled;
}

function sources(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return entry.name === "node_modules" ? [] : sources(path);
    return /\.tsx?$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name) ? [path] : [];
  });
}

const scanned = [
  ...sources(join(REPO, "app/capabilities")).filter((path) => path.includes("/web/")),
  ...sources(join(WEB, "lib")),
  ...sources(join(WEB, "components")),
];

describe("the type scale's census", () => {
  it("carries no off-scale text utility in capability, lib or component sources", () => {
    const offences: string[] = [];
    let seen = 0;
    for (const file of scanned) {
      for (const [, value] of readFileSync(file, "utf8").matchAll(CLASS)) {
        seen += 1;
        for (const utility of value.split(/\s+/)) {
          if (!isAllowedTextUtility(utility)) offences.push(`${relative(REPO, file)}: ${utility}`);
        }
      }
    }
    // A gate that walks an empty set passes vacuously; the source tree is not empty.
    expect(seen).toBeGreaterThan(250);
    expect(offences).toEqual([]);
  });
});

describe("the area hues", () => {
  /**
   * An area hue is an identity accent inside its own area's surfaces (O-2):
   * the rail's icon, an eyebrow label, a sparkline, a progress fill, a
   * status pill's text, one cover ground. Never a control's fill — and the
   * gate can say so, because the controls are painted by the shared
   * primitives, which stay neutral: an area hue that cannot reach
   * `web/ui/` cannot paint a button.
   */
  const AREA_HUE = /\b(?:text|bg|border)-area-[a-z]+\b/g;

  /** The files that may wear an area hue. */
  function mayWearAreaHues(file: string): boolean {
    // The rail's icons are the area's identity mark.
    if (file.endsWith("components/IconRail.tsx")) return true;
    // The map's home, beside the tokens.
    if (file.endsWith("lib/area.ts")) return true;
    // The area's own surfaces: a capability's own pages.
    return file.includes("/capabilities/") && file.includes("/web/");
  }

  /** The area hues a file wears that it may not. */
  function offences(file: string, source: string): string[] {
    if (mayWearAreaHues(file)) return [];
    return [...source.matchAll(AREA_HUE)].map((match) => `${relative(REPO, file)}: ${match[0]}`);
  }

  it("stay inside the area's own surfaces", () => {
    const found = scanned.flatMap((file) => offences(file, readFileSync(file, "utf8")));
    expect(found).toEqual([]);
  });

  it("admits the accent roles and refuses the rest", () => {
    // The roles O-2 names, in the area's own page: an eyebrow label, a
    // sparkline's stroke, a progress fill, a status pill's text. The page
    // wears its own area's hue; which hue belongs to which capability is
    // the areas' own business.
    const allowed = [
      'className="text-eyebrow text-area-writing uppercase"',
      '<svg className="text-area-writing" />',
      '<div className="h-1 rounded-full bg-area-writing" />',
      '<span className="rounded-full bg-area-writing/10 text-area-writing">Entwurf</span>',
    ];
    // The shell's chrome is neutral, and so are the primitives that paint
    // the controls.
    const refused = [
      ["web/components/TopBar.tsx", 'className="text-area-writing"'],
      ["web/ui/Button.tsx", 'className="bg-area-writing"'],
      ["web/ui/field.tsx", 'className="border-area-planning"'],
    ];
    const page = join(REPO, "app/capabilities/writing/web/NovelsPage.tsx");
    const shell = join(REPO, "web/components/TopBar.tsx");
    const wrong: string[] = [];
    for (const source of allowed) {
      // Admitted in the area's own page…
      if (offences(page, source).length > 0) wrong.push(`refused: ${source}`);
      // …and refused in the shell's chrome, where the same hue is an
      // offence. Without this second half the first is vacuous: the page's
      // path is allowlisted, so any source would pass there.
      if (offences(shell, source).length === 0) wrong.push(`admitted in the shell: ${source}`);
    }
    for (const [file, source] of refused) {
      if (offences(join(REPO, file), source).length === 0) wrong.push(`admitted: ${source}`);
    }
    expect(wrong).toEqual([]);
  });
});

describe("the scale's steps", () => {
  it("reads 11 / 12 / 13 / 14 / 15 / 20 / 28 with the design's leading", () => {
    const wrong: string[] = [];
    for (const [name, step] of Object.entries(SCALE)) {
      const size = token(`text-${name}`);
      if (size !== step.size) wrong.push(`--text-${name}: ${size} ≠ ${step.size}`);
      const leading = token(`text-${name}--line-height`);
      if (leading !== step.leading) {
        wrong.push(`--text-${name}--line-height: ${leading} ≠ ${step.leading}`);
      }
      const weight = token(`text-${name}--font-weight`);
      if (weight !== step.weight) {
        wrong.push(`--text-${name}--font-weight: ${weight} ≠ ${step.weight}`);
      }
      if (step.tracking !== undefined) {
        const tracking = token(`text-${name}--letter-spacing`);
        if (tracking !== step.tracking) {
          wrong.push(`--text-${name}--letter-spacing: ${tracking} ≠ ${step.tracking}`);
        }
      }
    }
    expect(wrong).toEqual([]);
  });

  it("carries no step outside the census", () => {
    // The theme's size tokens are the scale: a step the design does not name
    // is an off-scale utility waiting for a call site.
    const declared = [...CSS.matchAll(/--text-([a-z][a-z0-9]*):/g)].map((match) => match[1]);
    expect(declared.sort()).toEqual(Object.keys(SCALE).sort());
  });
});

describe("the prose's own headings", () => {
  it("lands the chapter headings on 26/34 and 21/28 px", () => {
    // The manuscript's body is 18 px; the rhythm rules are in `em`, so a
    // heading's size is its em step over the body and its leading the norm's
    // pair over the heading's own size.
    const body = Number(rule(".ProseMirror")["font-size"].replace("rem", "")) * 16;
    const wrong: string[] = [];
    for (const [selector, size, leading] of [
      [".ProseMirror h1", 26, 34],
      [".ProseMirror h2", 21, 28],
    ] as const) {
      const declarations = rule(selector);
      const measuredSize = Number(declarations["font-size"].replace("em", "")) * body;
      const measuredLeading = Number(declarations["line-height"]) * measuredSize;
      if (Math.round(measuredSize) !== size) {
        wrong.push(`${selector}: ${measuredSize.toFixed(2)}px ≠ ${size}px`);
      }
      if (Math.round(measuredLeading) !== leading) {
        wrong.push(`${selector}: ${measuredLeading.toFixed(2)}px ≠ ${leading}px`);
      }
    }
    expect(wrong).toEqual([]);
  });

  it("keeps the headings on the serif's own 600", () => {
    const shared = rule(
      ".ProseMirror h1",
      ".ProseMirror h2",
      ".ProseMirror h3",
      ".ProseMirror h4",
      ".ProseMirror h5",
      ".ProseMirror h6",
    );
    expect(shared["font-weight"]).toBe("600");
  });
});

describe("the paper's utilities", () => {
  it("draws the drop cap with the drafted metrics", () => {
    const cap = utilitiesRule(
      ".drop-cap .ProseMirror > p:first-of-type::first-letter",
    );
    expect(cap["float"]).toBe("left");
    expect(cap["font-size"]).toBe("4.5rem");
    expect(cap["line-height"]).toBe("0.8");
    // The serif's real 600 cut — no synthesized 700, the headings' rule.
    expect(cap["font-weight"]).toBe("600");
    expect(cap["color"]).toBe("var(--primary)");
    expect(cap["font-family"]).toContain('"EB Garamond"');
    expect(cap["margin-right"]).toBe("0.75rem");
  });

  it("inks the running head in the serif's italic, muted voice", () => {
    const head = utilitiesRule(".paper-runhead");
    expect(head["font-style"]).toBe("italic");
    expect(head["color"]).toBe("var(--muted)");
    expect(head["font-family"]).toContain('"EB Garamond"');
    // No opacity: the draft's 70% would drop the muted ink below AA on the
    // card (2.82:1 light); the token alone reads 5.05:1 / 4.53:1.
    expect(head["opacity"]).toBeUndefined();
  });

  it("inks the ghost in the writing hue at the drafted strength", () => {
    const ghost = rule(".ProseMirror .ghost");
    expect(ghost["font-style"]).toBe("italic");
    // The drafted 70%, carried by the document's ink: alpha over the card
    // measures 3.18:1 (light) / 3.75:1 (dark) — below AA; this mix keeps
    // the hue's strength and reads 8.25:1 / 7.65:1.
    expect(ghost["color"]).toBe(
      "color-mix(in srgb, var(--area-writing) 70%, var(--foreground))",
    );
  });
});

describe("the scale's utilities", () => {
  it("compiles the eyebrow to the drafted step", async () => {
    const css = await compileCss();
    const eyebrow = css.match(/\.text-eyebrow\s*\{([^}]*)\}/)?.[1] ?? "";
    // 11 px, the norm's 16 px leading, weight 600 and 0.08 em of tracking.
    expect(eyebrow).toMatch(/font-size:\s*0\.6875rem/);
    expect(eyebrow).toMatch(/line-height:[^;]*1\.45/);
    expect(eyebrow).toMatch(/font-weight:[^;]*600/);
    expect(eyebrow).toMatch(/letter-spacing:[^;]*0\.08em/);
  });

  it("keeps the hero on the real 700 cut", async () => {
    const css = await compileCss();
    const hero = css.match(/\.text-hero\s*\{([^}]*)\}/)?.[1] ?? "";
    expect(hero).toMatch(/font-size:\s*1\.875rem/);
    expect(hero).toMatch(/line-height:[^;]*1\.2/);
    expect(hero).toMatch(/font-weight:[^;]*700/);
  });

  it("gives every step the weight the design names", async () => {
    const css = await compileCss();
    for (const [name, step] of Object.entries(SCALE)) {
      const utility = css.match(new RegExp(`\\.text-${name}\\s*\\{([^}]*)\\}`))?.[1] ?? "";
      // The step's weight is the fallback of the variable a call site's
      // `font-*` utility sets.
      expect(utility).toMatch(new RegExp(`font-weight:[^;]*${step.weight}`));
    }
  });

  it("leaves a call site's font utility in charge of the weight", async () => {
    const css = await compileCss();
    // A step reads its weight from the variable Tailwind's font-weight
    // utilities set (`font-weight: var(--tw-font-weight, 500)`), so a call
    // site's own `font-medium` or `font-semibold` still wins over the step's
    // token weight — the override the call sites rely on.
    expect(css).toMatch(/\.text-label\s*\{[^}]*font-weight:\s*var\(--tw-font-weight,\s*500\)/);
    expect(css).toMatch(/\.font-medium\s*\{[^}]*--tw-font-weight:\s*var\(--font-weight-medium\)/);
    expect(css).toMatch(/\.font-semibold\s*\{[^}]*--tw-font-weight:\s*var\(--font-weight-semibold\)/);
  });

  it("has Tailwind's own tabular figures, so no custom utility is needed", async () => {
    const css = await compileCss();
    const tabular = css.match(/\.tabular-nums\s*\{([^}]*)\}/)?.[1] ?? "";
    expect(tabular).toMatch(/font-variant-numeric/);
    expect(tabular).toMatch(/tabular-nums/);
    // The eyebrow's uppercase rides with the usage, so the transform has to
    // be Tailwind's own.
    expect(css).toMatch(/\.uppercase\s*\{[^}]*text-transform:\s*uppercase/);
  });
});
