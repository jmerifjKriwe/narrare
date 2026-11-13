// @vitest-environment jsdom
/**
 * The rail's drafted tension arc (screens/writing/workspace.html, the
 * "Spannungsbogen" widget): the area-writing gradient curve with the
 * current chapter's marker riding it at position/total, the chapter the
 * caption names, and the placeholder where the draft wears an act name —
 * plot data the app does not hold, so the meta says so in words instead of
 * inventing one (spec §6's interim rule). The drawing paints in tokens,
 * never hexes, and stays hidden from the reader; the caption is real text.
 */
import { cleanup, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { afterEach, describe, expect, it } from "vitest";

import { t } from "@shell/lib/i18n";

import { StoryArc } from "./novel/StoryArc";

afterEach(cleanup);

describe("the drafted arc", () => {
  it("wears the drafted eyebrow and the placeholder where the act name stands", () => {
    render(<StoryArc position={1} total={3} />);
    expect(screen.getByText(t("workspace.railArcLabel"))).toBeTruthy();
    // The draft reads "Akt I - Höhepunkt"; the app holds no acts or beats.
    // The meta names the gap in words — never an invented act.
    expect(screen.getByText(t("workspace.railArcNone"))).toBeTruthy();
  });

  it("rides the marker on the curve at position/total", () => {
    const { container } = render(<StoryArc position={1} total={3} />);
    const marker = container.querySelector("svg circle");
    expect(marker).toBeTruthy();
    // One third along the draft's 200-wide path: the point of the curve
    // whose x is 200/3 — the draft's own marker for chapter 1 of 3.
    expect(Number(marker!.getAttribute("cx"))).toBeCloseTo(66.67, 1);
    expect(Number(marker!.getAttribute("cy"))).toBeCloseTo(23.09, 1);
  });

  it("re-derives the marker and the caption when the position changes", () => {
    const { container } = render(<StoryArc position={2} total={3} />);
    const marker = container.querySelector("svg circle");
    expect(Number(marker!.getAttribute("cx"))).toBeCloseTo(133.33, 1);
    expect(Number(marker!.getAttribute("cy"))).toBeCloseTo(10.39, 1);
    expect(screen.getByText(t("workspace.railArcChapter", { n: 2 }))).toBeTruthy();
    expect(screen.queryByText(t("workspace.railArcChapter", { n: 1 }))).toBeNull();
  });

  it("reaches the path's end at the book's last chapter", () => {
    const { container } = render(<StoryArc position={3} total={3} />);
    const marker = container.querySelector("svg circle");
    expect(Number(marker!.getAttribute("cx"))).toBeCloseTo(200, 1);
    expect(Number(marker!.getAttribute("cy"))).toBeCloseTo(34, 1);
  });

  it("stays a labeled curve when no chapter is open", () => {
    const { container } = render(<StoryArc position={0} total={3} />);
    expect(container.querySelector("svg circle")).toBeNull();
    expect(screen.queryByText(t("workspace.railArcChapter", { n: 0 }))).toBeNull();
    expect(screen.getByText(t("workspace.railArcLabel"))).toBeTruthy();
  });

  it("guards the empty book: a zero total never divides", () => {
    const { container } = render(<StoryArc position={0} total={0} />);
    expect(container.querySelector("svg circle")).toBeNull();
  });

  it("paints in tokens, never hexes", () => {
    const { container } = render(<StoryArc position={1} total={3} />);
    // The draft's three gradient stops are one hue at three depths; the
    // token's value at the draft's opacities is the honest translation.
    const stops = [...container.querySelectorAll("svg stop")];
    expect(stops).toHaveLength(3);
    for (const stop of stops) {
      expect(stop.getAttribute("stop-color")).toBe("var(--area-writing)");
    }
    expect(container.querySelector("svg circle")!.getAttribute("fill")).toBe(
      "var(--area-writing)",
    );
    // No literal colour anywhere — the one `#` the draft's vocabulary has
    // is the gradient's `url(#id)` reference, not a hex.
    expect(
      /#[0-9a-fA-F]{3,8}\b/.test(container.innerHTML.replace(/url\(#\w+\)/g, "")),
    ).toBe(false);
  });

  it("hides the drawing from the reader and keeps the caption as text", () => {
    const { container } = render(<StoryArc position={1} total={3} />);
    expect(container.querySelector("svg")!.getAttribute("aria-hidden")).toBe("true");
    expect(screen.getByText(t("workspace.railArcChapter", { n: 1 }))).toBeTruthy();
  });

  it("carries the interim comment with its follow-up anchor", () => {
    const source = readFileSync("../app/capabilities/writing/web/novel/StoryArc.tsx", "utf8");
    expect(source).toContain("// interim: no plot data — #817");
  });
});
