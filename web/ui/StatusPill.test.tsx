// @vitest-environment jsdom
/**
 * The status pill's contract (spec §5.9): the drafted shelf's four states,
 * each an eyebrow-tracked span wearing its own ground/ink/rule triple — the
 * light halves extracted from `shelf.html`, the dark halves literal from
 * `shelf-dark.html` (the screen wins over the token card, D-6). The labels
 * are the writing catalog's own, so a pill speaks the reader's language.
 *
 * The token values are pinned in `globals.css` itself, and the inks are
 * measured against their grounds here: AA 4.5:1 in both themes, the same
 * bar the shell's own contrast table keeps. A value that fell below it
 * would fail this file rather than be adjusted quietly.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { t, type MessageKey } from "../lib/i18n";

import { StatusPill, type StatusKind } from "./StatusPill";

// Vitest runs with the web root as its cwd (the same assumption
// `IconRail.test.tsx` makes when it reads the stylesheet).
const WEB = process.cwd();
const CSS = readFileSync(join(WEB, "globals.css"), "utf8");

/**
 * Each kind's catalog label and its drafted triplet: light (ground, ink —
 * the drafted light pill draws no rule) and dark (ground, ink, rule).
 */
const PILLS: Record<
  StatusKind,
  { label: MessageKey; light: [string, string]; dark: [string, string, string] }
> = {
  active: {
    label: "shelf.hero.active",
    light: ["#FED8CA", "#795C52"],
    dark: ["#1B3520", "#66BB6A", "#25502C"],
  },
  draft: {
    label: "shelf.statusDraft",
    light: ["#FED8CA", "#795C52"],
    dark: ["#192D3E", "#64B5F6", "#234561"],
  },
  planning: {
    label: "shelf.statusPlanning",
    light: ["#EEE7DF", "#53433D"],
    dark: ["#2C2C28", "#E0E0E0", "#3D3D37"],
  },
  review: {
    label: "shelf.statusReview",
    light: ["#EEE7DF", "#606127"],
    dark: ["#3A2814", "#FFB74D", "#5A3C1C"],
  },
};

/** The one `light-dark()` pair a token carries, light side first. */
function pair(name: string): [string, string] {
  const found = new RegExp(`--${name}:\\s*light-dark\\(([^,]+),\\s*([^)]+)\\)`).exec(CSS);
  if (found === null) {
    throw new Error(`globals.css has no --${name} light-dark() pair`);
  }
  return [found[1].trim(), found[2].trim()];
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

afterEach(cleanup);

describe("StatusPill", () => {
  it("renders a span carrying the kind's catalog label", () => {
    for (const [kind, pill] of Object.entries(PILLS) as [
      StatusKind,
      (typeof PILLS)[StatusKind],
    ][]) {
      const { container, unmount } = render(<StatusPill kind={kind} />);
      const span = container.querySelector("span");
      expect(span, kind).not.toBeNull();
      expect(span?.tagName, kind).toBe("SPAN");
      expect(span?.textContent, kind).toBe(t(pill.label));
      unmount();
    }
  });

  it("wears its own token utilities on the eyebrow step", () => {
    for (const kind of Object.keys(PILLS) as StatusKind[]) {
      const { container, unmount } = render(<StatusPill kind={kind} />);
      const classes = container.querySelector("span")?.className ?? "";
      expect(classes, kind).toContain(`bg-pill-${kind}-ground`);
      expect(classes, kind).toContain(`text-pill-${kind}-ink`);
      expect(classes, kind).toContain(`border-pill-${kind}-rule`);
      expect(classes, kind).toContain("text-eyebrow");
      expect(classes, kind).toContain("uppercase");
      unmount();
    }
  });

  it("carries no literal colour: the tokens are the one palette", () => {
    const source = readFileSync(join(WEB, "ui/StatusPill.tsx"), "utf8");
    // Six- or eight-digit literals, or one inside a utility's brackets; the
    // three-digit issue references in the comments are not colours.
    expect(source).not.toMatch(/#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?\b/);
    expect(source).not.toMatch(/(?:bg|text|border|ring|fill|stroke)-\[#[0-9A-Fa-f]{3,8}\]/);
  });

  it("pins the drafted triples in globals.css", () => {
    for (const [kind, pill] of Object.entries(PILLS) as [
      StatusKind,
      (typeof PILLS)[StatusKind],
    ][]) {
      expect(pair(`pill-${kind}-ground`), kind).toEqual([pill.light[0], pill.dark[0]]);
      expect(pair(`pill-${kind}-ink`), kind).toEqual([pill.light[1], pill.dark[1]]);
      // The drafted light pill draws no border; the dark screen's rule binds.
      expect(pair(`pill-${kind}-rule`), kind).toEqual(["transparent", pill.dark[2]]);
    }
    // The accent the dark shelf draws for the writing area (§5.9, D-6).
    expect(pair("area-writing")).toEqual(["#914F2F", "#E28659"]);
  });

  it("surfaces every triple as a utility", () => {
    // The pill's classes are only paint if `@theme inline` exposes each
    // token; a missing line would leave the utility inert and the pill bare.
    for (const kind of Object.keys(PILLS) as StatusKind[]) {
      for (const part of ["ground", "ink", "rule"]) {
        expect(CSS).toContain(
          `--color-pill-${kind}-${part}: var(--pill-${kind}-${part});`,
        );
      }
    }
  });

  describe("measures AA in both themes", () => {
    /**
     * The inks on their grounds, measured here (WCAG relative luminance):
     *
     * | kind     | light | dark  |
     * |----------|-------|-------|
     * | active   | 4.58  | 5.63  |
     * | draft    | 4.58  | 6.38  |
     * | planning | 7.65  | 10.62 |
     * | review   | 5.29  | 8.12  |
     */
    const RECORDED: Record<StatusKind, Record<"light" | "dark", number>> = {
      active: { light: 4.58, dark: 5.63 },
      draft: { light: 4.58, dark: 6.38 },
      planning: { light: 7.65, dark: 10.62 },
      review: { light: 5.29, dark: 8.12 },
    };

    it("clears the 4.5:1 text bar at the recorded ratios", () => {
      // The value pin above proves the stylesheet carries the PILLS triples,
      // so measuring those triples measures what the pill paints.
      const wrong: string[] = [];
      for (const [kind, pill] of Object.entries(PILLS) as [
        StatusKind,
        (typeof PILLS)[StatusKind],
      ][]) {
        for (const theme of ["light", "dark"] as const) {
          const ink = theme === "light" ? pill.light[1] : pill.dark[1];
          const ground = theme === "light" ? pill.light[0] : pill.dark[0];
          const measured = Number(contrast(ink, ground).toFixed(2));
          if (measured < 4.5) {
            wrong.push(`${kind} ${theme}: ${measured}:1 (needs 4.5)`);
          }
          if (measured !== RECORDED[kind][theme]) {
            wrong.push(`${kind} ${theme}: ${measured} ≠ recorded ${RECORDED[kind][theme]}`);
          }
        }
      }
      expect(wrong).toEqual([]);
    });
  });
});
