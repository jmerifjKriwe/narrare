// @vitest-environment node
/**
 * The scale's gate. The census in spec §11 is a command a human runs; this is
 * the same measurement in the suite, so a `text-lg` cannot ride in unnoticed
 * (#544, #573). Only `className="…"` literals are read — the shape §11
 * measures; `className={…}` templates are outside it on purpose.
 */
import { readFileSync, readdirSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const WEB = new URL("..", import.meta.url).pathname;
const REPO = new URL("../..", import.meta.url).pathname;
const OFF_SCALE = /^text-(sm|base|lg|xl|2xl|3xl)$/;
const CLASS = /className="([^"]*)"/g;

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
        for (const token of value.split(/\s+/)) {
          if (OFF_SCALE.test(token)) offences.push(`${relative(REPO, file)}: ${token}`);
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
    const wrong: string[] = [];
    for (const source of allowed) {
      if (offences(page, source).length > 0) wrong.push(`refused: ${source}`);
    }
    for (const [file, source] of refused) {
      if (offences(join(REPO, file), source).length === 0) wrong.push(`admitted: ${source}`);
    }
    expect(wrong).toEqual([]);
  });
});

describe("the scale's steps", () => {
  it("reads 12 / 13 / 14 / 15 / 20 / 28", () => {
    const css = readFileSync(join(WEB, "globals.css"), "utf8");
    const step = (name: string) =>
      new RegExp(`--text-${name}: ([\\d.]+)rem;`).exec(css)?.[1] ?? null;
    expect(
      Object.fromEntries(
        ["meta", "label", "body", "emph", "title", "hero"].map((name) => [name, step(name)]),
      ),
    ).toEqual({
      meta: "0.75",
      label: "0.8125",
      body: "0.875",
      emph: "0.9375",
      title: "1.25",
      hero: "1.75",
    });
  });
});
