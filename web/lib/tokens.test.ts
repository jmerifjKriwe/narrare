// @vitest-environment node
/**
 * The tokens' gate: the shell's colours are the design's, not ours.
 *
 * The norm is `docs/design/stitch/DESIGN.md` (light) and
 * `docs/design/stitch/dark-tokens.md` (dark, measured). This parses
 * `web/globals.css` and asserts that every pair the spec's §6.2 names
 * resolves to exactly those values, so a token cannot drift into a shade
 * the drafts never showed. One pair follows the screens rather than
 * DESIGN.md's named value: `--card`, which the drafted shelf paints on the
 * parchment surface `#FFF8F2` instead of `bg-card-light`'s `#FFFFFF` (spec
 * §6.2's screen rule). The cover aliases in `@theme inline` are gated too:
 * a utility reads the alias, and one pointed at another token's variable
 * would pass the pair gate and paint a wrong-coloured cover.
 *
 * The contrast table is the same measurement the axe leg makes, done here
 * where a failure names the pair instead of a selector: the ink, the ground
 * it rides and the bar it must clear. The cover's gate goes one step further
 * (R15): it composites each text role's ink over its ground at the dim the
 * component renders (`COVER_TEXT_DIMS` in cover.ts), so the AA promise covers
 * the dimmed render a reader actually sees, not just the full-ink token pair.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import {
  CHANNEL_TOKENS,
  COVER_TEXT_DIMS,
  type CoverChannel,
  type CoverTextDims,
} from "./cover/cover";

const WEB = new URL("..", import.meta.url).pathname;
const CSS = readFileSync(join(WEB, "globals.css"), "utf8");

/** The `:root` block's body — the shell's one token surface. */
function rootBlock(): string {
  const at = CSS.indexOf(":root {");
  if (at < 0) throw new Error("globals.css has no :root block");
  const open = CSS.indexOf("{", at);
  let depth = 0;
  for (let i = open; i < CSS.length; i += 1) {
    if (CSS[i] === "{") depth += 1;
    else if (CSS[i] === "}") {
      depth -= 1;
      if (depth === 0) return CSS.slice(open + 1, i);
    }
  }
  throw new Error("globals.css's :root block never closes");
}

/** The `@theme inline` block's body — the Tailwind aliases the utilities read. */
function themeBlock(): string {
  const at = CSS.indexOf("@theme inline {");
  if (at < 0) throw new Error("globals.css has no @theme inline block");
  const open = CSS.indexOf("{", at);
  let depth = 0;
  for (let i = open; i < CSS.length; i += 1) {
    if (CSS[i] === "{") depth += 1;
    else if (CSS[i] === "}") {
      depth -= 1;
      if (depth === 0) return CSS.slice(open + 1, i);
    }
  }
  throw new Error("globals.css's @theme inline block never closes");
}

/** The block's own declarations, name → value. CSS comments are stripped
 * first, so a commented-out declaration cannot witness a gate. */
function declarations(source: string): Record<string, string> {
  const found: Record<string, string> = {};
  const live = source.replace(/\/\*[\s\S]*?\*\//g, "");
  for (const match of live.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) {
    found[match[1].slice(2)] = match[2].replace(/\s+/g, " ").trim();
  }
  return found;
}

/** Split on the commas that separate a value's own parts, not a nested one's. */
function parts(value: string): string[] {
  const out: string[] = [];
  let depth = 0;
  let start = 0;
  for (let i = 0; i < value.length; i += 1) {
    const char = value[i];
    if (char === "(") depth += 1;
    else if (char === ")") depth -= 1;
    else if (char === "," && depth === 0) {
      out.push(value.slice(start, i).trim());
      start = i + 1;
    }
  }
  out.push(value.slice(start).trim());
  return out;
}

/**
 * The value as the theme resolves it: `light-dark()` folds to one side and
 * `var()` reads the token it names, so the measurement below runs against the
 * values the browser will actually paint.
 */
function resolve(
  value: string,
  theme: "light" | "dark",
  tokens: Record<string, string>,
  depth = 0,
): string {
  if (depth > 12) return value;
  const lightDark = /light-dark\(/.exec(value);
  if (lightDark) {
    const open = lightDark.index + "light-dark(".length;
    let close = open;
    let depthInner = 1;
    while (close < value.length && depthInner > 0) {
      if (value[close] === "(") depthInner += 1;
      else if (value[close] === ")") depthInner -= 1;
      close += 1;
    }
    const [light, dark] = parts(value.slice(open, close - 1));
    return resolve(
      value.slice(0, lightDark.index) + (theme === "light" ? light : dark) + value.slice(close),
      theme,
      tokens,
      depth + 1,
    );
  }
  const reference = /var\((--[\w-]+)\)/.exec(value);
  if (reference) {
    const named = tokens[reference[1].slice(2)];
    if (named === undefined) return value;
    return resolve(
      value.replace(reference[0], resolve(named, theme, tokens, depth + 1)),
      theme,
      tokens,
      depth + 1,
    );
  }
  return value;
}

/** The token's value in one theme. */
function painted(tokens: Record<string, string>, name: string, theme: "light" | "dark"): string {
  const value = tokens[name];
  if (value === undefined) throw new Error(`globals.css has no --${name}`);
  return resolve(value, theme, tokens);
}

/** WCAG relative luminance of a hex colour. */
function luminance(hex: string): number {
  const value = hex.replace("#", "");
  if (!/^[0-9A-Fa-f]{6}$/.test(value)) throw new Error(`not a hex colour: ${hex}`);
  const channels = [0, 2, 4].map((at) => {
    const part = parseInt(value.slice(at, at + 2), 16) / 255;
    return part <= 0.04045 ? part / 12.92 : ((part + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

/** The WCAG contrast ratio of two hex colours. */
function contrast(ink: string, ground: string): number {
  const [high, low] = [luminance(ink), luminance(ground)].sort((a, b) => b - a);
  return (high + 0.05) / (low + 0.05);
}

/**
 * The colour a dimmed text role actually paints: the ink composited over the
 * ground in sRGB, `dim * ink + (1 - dim) * ground` per channel, rounded to the
 * 8-bit value the screen shows. The pair gate measures full ink; this is the
 * colour the reader's eye meets at the rendered opacity.
 */
function dimmed(ink: string, ground: string, dim: number): string {
  const channels = (hex: string) => [0, 2, 4].map((at) => parseInt(hex.slice(at + 1, at + 3), 16));
  const from = channels(ink);
  const over = channels(ground);
  const mixed = from.map((value, i) => Math.round(dim * value + (1 - dim) * over[i]));
  return `#${mixed.map((value) => value.toString(16).padStart(2, "0")).join("")}`;
}

/**
 * The pairs the spec's §6.2 names, light and dark: the norm's own values
 * (DESIGN.md for the light half, the measured dark half from
 * `dark-tokens.md`).
 */
const PAIRS: Record<string, [string, string]> = {
  // The page and its chrome: the parchment ground, the panel above it, the
  // card above that, and the wash between them.
  background: ["#F6F3ED", "#16140F"],
  foreground: ["#1E1B16", "#DFDEDA"],
  muted: ["#6E6B65", "#89867F"],
  panel: ["#FDFCF9", "#1C1914"],
  card: ["#FFF8F2", "#211F1A"],
  soft: ["#EFEBE2", "#2C2922"],
  border: ["#E0DEDA", "#35332D"],
  rule: ["#EEEBE5", "#302D28"],
  // The one action's colour and the ink that rides it; the keyboard's ring.
  primary: ["#743B1F", "#D39562"],
  "primary-foreground": ["#FAF8F5", "#1D140D"],
  focus: ["#8F4622", "#F2AD73"],
  // The surface ladder: the steps between the canvas and the card, and the
  // hairlines that separate them.
  surface: ["#FFF8F2", "#211F1A"],
  "surface-container-lowest": ["#FFFFFF", "#100E0A"],
  "surface-container-low": ["#FAF2EA", "#191611"],
  "surface-container": ["#F4EDE4", "#211F1A"],
  "surface-container-high": ["#EEE7DF", "#27241E"],
  "surface-container-highest": ["#E9E1D9", "#2E2A23"],
  "surface-variant": ["#E9E1D9", "#3A352C"],
  outline: ["#86736C", "#564E43"],
  "outline-variant": ["#D8C2B9", "#3D372E"],
  // The second voice: the terracotta-rose the design keeps for the surfaces
  // that are not the one action.
  secondary: ["#74584E", "#D7A892"],
  "secondary-foreground": ["#FFFFFF", "#3B1C10"],
  "secondary-container": ["#FED8CA", "#47291D"],
  "secondary-container-foreground": ["#795C52", "#FED8CA"],
  // The inverse pair: what a surface floating above the page dims the page
  // with, and the ink that rides on it.
  "inverse-surface": ["#33302B", "#EDE0D4"],
  "inverse-foreground": ["#F7F0E7", "#211F1A"],
  "inverse-primary": ["#FFB695", "#743B1F"],
  // The diagnostic states.
  success: ["#21763C", "#52D47E"],
  warning: ["#9A6100", "#E5A84B"],
  danger: ["#AC3031", "#F27474"],
  // The five areas' identity marks.
  "area-writing": ["#914F2F", "#D88D68"],
  "area-knowledge": ["#606127", "#B4B65B"],
  "area-chat": ["#3A637B", "#72A5C3"],
  "area-planning": ["#834D7E", "#C686C0"],
  "area-settings": ["#5A5549", "#ABA391"],
  // The book object's own grounds and inks: the covers keep their tones in
  // both themes, raised where the dark ground would swallow them.
  "cover-pale": ["#EEEBE5", "#E8E2D7"],
  "cover-pale-ink": ["#1E1B16", "#24211C"],
  "cover-sepia": ["#743B1F", "#5D2F17"],
  "cover-sepia-ink": ["#FFF8F2", "#FFF8F2"],
  "cover-ink": ["#24211C", "#181512"],
  "cover-ink-ink": ["#FFF8F2", "#DFDEDA"],
  "cover-slate": ["#3A637B", "#284457"],
  "cover-slate-ink": ["#FFF8F2", "#FFF8F2"],
  // The procedural cover's four genre grounds (cover-system spec, Sektion
  // 02): theme-constant in both halves, the spec's no-inversion rule
  // (Sektion 06) — a book keeps its pigment on the midnight shelf, and the
  // rim-light that keeps it off the canvas is the component's own.
  "cover-fantasy": ["#2C382E", "#2C382E"],
  "cover-fantasy-ink": ["#FFF8F2", "#FFF8F2"],
  "cover-romance": ["#633B3E", "#633B3E"],
  "cover-romance-ink": ["#FFF8F2", "#FFF8F2"],
  "cover-thriller": ["#1D2228", "#1D2228"],
  "cover-thriller-ink": ["#FFF8F2", "#FFF8F2"],
  "cover-fallback": ["#DFD7CB", "#DFD7CB"],
  "cover-fallback-ink": ["#1E1B16", "#1E1B16"],
  // The blind-deboss boundary's gold (cover-system spec, Sektion 01): the
  // draft's Tailwind amber-300, theme-constant like the genre grounds. Kept
  // in oklch — the value sits a hair outside sRGB, and a hex would clip its
  // red channel into a different gold. A decorative hairline that carries
  // no information of its own, so it has no contrast row (the outline
  // hairline's rule).
  "cover-deboss": ["oklch(87.9% 0.169 91.605)", "oklch(87.9% 0.169 91.605)"],
};

/** The shape ladder (spec §6.4): 4 px small controls, 8 px controls, 12 px surfaces. */
const RADII: Record<string, string> = {
  "radius-sm": "4px",
  "radius-control": "8px",
  "radius-surface": "12px",
  // The names the app's call sites still spell; they alias the ladder's two
  // lower steps until the call sites move onto the role names.
  radius: "4px",
  "radius-lg": "8px",
};

/** The card's ambient shadow, per theme (DESIGN.md's layer tiers). */
const SHADOW_CARD = {
  light: ["0 1px 3px 0 rgba(44, 24, 16, 0.05)", "0 1px 2px -1px rgba(44, 24, 16, 0.03)"],
  dark: ["0 1px 3px 0 rgba(0, 0, 0, 0.35)"],
};

/**
 * Two pairs the norm itself puts below the bar are not in the table, and
 * their measured values are the ones to keep in mind: the muted ink on the
 * selection wash (4.46:1 light, 3.99:1 dark — the app keeps off it; a row's
 * ink on the wash is foreground ink, the rule the design docs draw —
 * `docs/design/stitch/DESIGN.md`, `dark-tokens.md`) and the hairline
 * outline (4.05:1 light, 2.25:1 dark — a rule that carries no information
 * of its own, and outside axe's A/AA rule set).
 */

/** The pairs the shell paints, and the bar each must clear. */
const TEXT_PAIRS: [string, string, number][] = [
  ["foreground", "background", 4.5],
  ["foreground", "panel", 4.5],
  ["foreground", "card", 4.5],
  ["foreground", "soft", 4.5],
  ["muted", "background", 4.5],
  ["muted", "panel", 4.5],
  ["muted", "card", 4.5],
  ["primary", "background", 4.5],
  ["primary", "card", 4.5],
  ["primary-foreground", "primary", 4.5],
  ["secondary-foreground", "secondary", 4.5],
  ["secondary-container-foreground", "secondary-container", 4.5],
  ["inverse-foreground", "inverse-surface", 4.5],
  ["success", "background", 4.5],
  ["success", "card", 4.5],
  ["warning", "background", 4.5],
  ["warning", "card", 4.5],
  ["danger", "background", 4.5],
  ["danger", "card", 4.5],
  ["cover-pale-ink", "cover-pale", 4.5],
  ["cover-sepia-ink", "cover-sepia", 4.5],
  ["cover-ink-ink", "cover-ink", 4.5],
  ["cover-slate-ink", "cover-slate", 4.5],
  ["cover-fantasy-ink", "cover-fantasy", 4.5],
  ["cover-romance-ink", "cover-romance", 4.5],
  ["cover-thriller-ink", "cover-thriller", 4.5],
  ["cover-fallback-ink", "cover-fallback", 4.5],
];

/** The marks that carry no text and still have to be seen: 3:1 (WCAG 1.4.11). */
const GRAPHICS_PAIRS: [string, string, number][] = [
  ["focus", "background", 3],
  ["focus", "card", 3],
  ["inverse-primary", "inverse-surface", 3],
  ["area-writing", "panel", 3],
  ["area-knowledge", "panel", 3],
  ["area-chat", "panel", 3],
  ["area-planning", "panel", 3],
  ["area-settings", "panel", 3],
  ["area-writing", "card", 3],
  ["area-knowledge", "card", 3],
  ["area-chat", "card", 3],
  ["area-planning", "card", 3],
  ["area-settings", "card", 3],
];

describe("the declarations reader", () => {
  it("strips CSS comments, so a commented-out declaration never witnesses a gate", () => {
    const source = [
      "--live: #FFF8F2;",
      "/* --single-line: #000000; */",
      "--beside: 4px; /* --trailing: #16140F; */",
      "/* a multi-line note",
      "   --buried: #743B1F;",
      "   that must not count */",
      "--after: 8px;",
    ].join("\n");
    expect(declarations(source)).toEqual({ live: "#FFF8F2", beside: "4px", after: "8px" });
  });
});

describe("the shell's tokens", () => {
  const tokens = declarations(rootBlock());

  it("resolves every pair to the norm's light and dark values", () => {
    const wrong: string[] = [];
    for (const [name, [light, dark]] of Object.entries(PAIRS)) {
      const value = tokens[name];
      if (value === undefined) {
        wrong.push(`--${name} is missing`);
        continue;
      }
      const paintedLight = painted(tokens, name, "light").toUpperCase();
      const paintedDark = painted(tokens, name, "dark").toUpperCase();
      // CSS colour values are case-insensitive: the oklch deboss gold reads
      // lowercase, the hex pairs uppercase; the comparison folds both.
      if (paintedLight !== light.toUpperCase())
        wrong.push(`--${name} light: ${paintedLight} ≠ ${light}`);
      if (paintedDark !== dark.toUpperCase())
        wrong.push(`--${name} dark: ${paintedDark} ≠ ${dark}`);
    }
    expect(wrong).toEqual([]);
  });

  it("carries the shape ladder of four, eight and twelve", () => {
    const wrong: string[] = [];
    for (const [name, expected] of Object.entries(RADII)) {
      const value = tokens[name];
      if (value === undefined) {
        wrong.push(`--${name} is missing`);
        continue;
      }
      const paintedValue = painted(tokens, name, "light");
      if (paintedValue !== expected) wrong.push(`--${name}: ${paintedValue} ≠ ${expected}`);
    }
    expect(wrong).toEqual([]);
  });

  it("carries the card's ambient shadow, per theme", () => {
    const value = tokens["shadow-card"];
    if (value === undefined) throw new Error("globals.css has no --shadow-card");
    // A fully transparent layer paints nothing: the dark shadow is the
    // design's one layer, whatever the token spells around it.
    const layers = (theme: "light" | "dark") =>
      parts(painted(tokens, "shadow-card", theme)).filter((layer) => !/transparent$/i.test(layer));
    expect(layers("light")).toEqual(SHADOW_CARD.light);
    expect(layers("dark")).toEqual(SHADOW_CARD.dark);
  });

  it("carries the brand serif once, as the token both surfaces read (R17)", () => {
    // One home for the stack: the prose surface consumes it here, the cover
    // title via `[font-family:var(--font-serif)]` (pinned in BookCover.test).
    expect(tokens["font-serif"]).toBe('"EB Garamond", Georgia, "Times New Roman", serif');
    expect(CSS).toContain("font-family: var(--font-serif);");
  });
});

describe("the cover's Tailwind aliases", () => {
  const aliases = declarations(themeBlock());

  it("points every cover token at its own variable", () => {
    const wrong: string[] = [];
    for (const name of Object.keys(PAIRS)) {
      if (!name.startsWith("cover-")) continue;
      const alias = `color-${name}`;
      const value = aliases[alias];
      if (value === undefined) {
        wrong.push(`--${alias} is missing`);
        continue;
      }
      const expected = `var(--${name})`;
      if (value !== expected) wrong.push(`--${alias}: ${value} ≠ ${expected}`);
    }
    expect(wrong).toEqual([]);
  });
});

describe("the shell's contrast table", () => {
  const tokens = declarations(rootBlock());

  it("clears AA on every pair the shell paints", () => {
    const wrong: string[] = [];
    for (const theme of ["light", "dark"] as const) {
      for (const [ink, ground, bar] of [...TEXT_PAIRS, ...GRAPHICS_PAIRS]) {
        const measured = contrast(
          painted(tokens, ink, theme),
          painted(tokens, ground, theme),
        );
        if (measured < bar) {
          wrong.push(`${theme}: ${ink} on ${ground} measures ${measured.toFixed(2)}:1 (needs ${bar})`);
        }
      }
    }
    expect(wrong).toEqual([]);
  });
});

describe("the cover's dimmed text (R15)", () => {
  const tokens = declarations(rootBlock());

  /** The dimmed roles a channel renders; the miniature keeps none of them. */
  const roles = (dims: CoverTextDims): Array<[string, number]> => [
    ["eyebrow", dims.eyebrow],
    ["author at wizard", dims.author.wizard],
    ["author at hero", dims.author.hero],
    ["author at shelf", dims.author.shelf],
    ["variant-2 foot", dims.foot],
  ];

  it("clears AA on every channel's dimmed roles in both themes", () => {
    const wrong: string[] = [];
    for (const theme of ["light", "dark"] as const) {
      for (const channel of Object.keys(CHANNEL_TOKENS) as CoverChannel[]) {
        const ground = painted(tokens, CHANNEL_TOKENS[channel].ground, theme);
        const ink = painted(tokens, CHANNEL_TOKENS[channel].ink, theme);
        for (const [role, dim] of roles(COVER_TEXT_DIMS[channel])) {
          const measured = contrast(dimmed(ink, ground, dim), ground);
          if (measured < 4.5) {
            wrong.push(
              `${theme} ${channel} ${role} at ${dim}: ${measured.toFixed(2)}:1 (needs 4.5)`,
            );
          }
        }
      }
    }
    expect(wrong).toEqual([]);
  });

  it("keeps every dim on the opacity scale the literal utilities emit", () => {
    const wrong: string[] = [];
    for (const [channel, dims] of Object.entries(COVER_TEXT_DIMS)) {
      for (const [role, dim] of roles(dims)) {
        const step = dim * 100;
        if (!(step > 0 && step <= 100 && Number.isInteger(step) && step % 5 === 0)) {
          wrong.push(`${channel} ${role}: ${dim} is not an opacity-<step> utility`);
        }
      }
    }
    expect(wrong).toEqual([]);
  });
});
