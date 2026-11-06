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
