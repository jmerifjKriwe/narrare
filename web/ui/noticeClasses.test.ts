// @vitest-environment jsdom
/**
 * Notice's class contract, pinned whole per tone: this helper is the app's
 * only error/empty/loading vocabulary — the census (P18) demands
 * `text-danger` = 0 outside this file — so a tone losing its colour, or a
 * fill sneaking under it, fails here, not in a screenshot. The drafted
 * finding-card shell (spec §6.5) rides the base: a hairline `--border`
 * edge on the surface radius, and the severity tones crown it with their
 * own colour as a 4 px rule on top — warning amber, danger rust — while
 * `info` and `quiet`, with nothing to raise, keep the plain edge. What no
 * tone may wear is a fill (the parked P1 rule: muted on soft is below AA);
 * the card is its edge and its rule, not a ground.
 *
 * The live → role wiring is rendered, not string-pinned: only the DOM can
 * pin that a caller's own `role` prop cannot override the `live` they
 * named — a pure helper would merely restate the mapping it replaced. The
 * actions row is rendered beside it for the same reason: the pair is the
 * caller's (the button matrix, never new button styles), and only the DOM
 * pins that the row carries what the caller handed it. The axe pass stays
 * with the E2E suites.
 */
import { createElement } from "react";
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { NOTICE_TONES, noticeClass, Notice } from "./Notice";

/** The drafted shell every tone wears: the edge, the radius, the wrap. */
const NOTICE_BASE =
  "flex flex-wrap items-center gap-2 rounded-[var(--radius-surface)] border border-border px-3 py-2 text-body";

const MATRIX: Record<(typeof NOTICE_TONES)[number], string> = {
  info: `${NOTICE_BASE} text-foreground`,
  warning: `${NOTICE_BASE} border-t-4 border-t-warning text-warning`,
  danger: `${NOTICE_BASE} border-t-4 border-t-danger text-danger`,
  quiet: `${NOTICE_BASE} text-muted`,
};

describe("noticeClass", () => {
  it("carries exactly the pinned string in every tone", () => {
    for (const tone of NOTICE_TONES) {
      expect(noticeClass(tone)).toBe(MATRIX[tone]);
    }
  });

  it("speaks the state colours and crowns the severity tones with their rule", () => {
    expect(noticeClass("danger")).toContain("text-danger");
    expect(noticeClass("danger")).toContain("border-t-4 border-t-danger");
    expect(noticeClass("warning")).toContain("border-t-4 border-t-warning");
    // The unraised tones keep the plain hairline: no severity to mark.
    expect(noticeClass("info")).not.toContain("border-t-");
    expect(noticeClass("quiet")).not.toContain("border-t-");
    expect(noticeClass("quiet")).toContain("text-muted");
  });

  it("never wears the legacy vocabulary, a primary fill or any fill at all", () => {
    for (const tone of NOTICE_TONES) {
      const classes = noticeClass(tone);
      expect(classes).not.toContain("text-sm");
      expect(classes).not.toContain("rounded-md");
      expect(classes).not.toContain("bg-primary");
      // The no-fill law: the card is its edge and its rule — no `--soft`
      // (muted on soft is below AA), no card, no panel.
      expect(classes).not.toContain("bg-");
    }
  });
});

describe("Notice's rendered shell", () => {
  afterEach(cleanup);

  /** The notice's root element, rendered from the given props. */
  function root(props: Record<string, unknown>): Element {
    const { container } = render(
      createElement(
        Notice,
        { tone: "danger", ...props },
        "Der Server ist unerreichbar.",
      ),
    );
    return container.firstElementChild as Element;
  }

  it("maps live to its role: alert interrupts, status informs", () => {
    expect(root({ live: "alert" }).getAttribute("role")).toBe("alert");
    expect(root({ live: "status" }).getAttribute("role")).toBe("status");
  });

  it("renders no role at all when live is none — the default", () => {
    const element = root({});
    expect(element.hasAttribute("role")).toBe(false);
    const explicit = root({ live: "none" });
    expect(explicit.hasAttribute("role")).toBe(false);
  });

  it("does not let a caller's role override the live mapping", () => {
    // The role is set after the prop spread on purpose: `live` is the
    // contract for the attribute, so a stray caller `role` cannot turn
    // an interrupting outage into a polite status.
    const element = root({ live: "alert", role: "status" });
    expect(element.getAttribute("role")).toBe("alert");
  });

  it("rides the one action at the far edge of the message row", () => {
    const element = root({ action: createElement("button", null, "Erneut versuchen") });
    const action = element.lastElementChild as Element;
    expect(action.className).toBe("ml-auto shrink-0");
    expect(action.textContent).toBe("Erneut versuchen");
  });

  it("renders the actions bar as its own full-width row below the message", () => {
    // The finding card's decision row: the caller's primary/ghost pair,
    // carried unchanged — the pair is the button matrix's, not a style
    // the notice grows. The row wraps under the message, so the plain
    // notice's DOM stays what it always was.
    const element = root({
      actions: createElement(
        "div",
        null,
        createElement("button", null, "Übernehmen"),
        createElement("button", null, "Verwerfen"),
      ),
    });
    const row = element.lastElementChild as Element;
    expect(row.className).toBe("flex w-full items-center gap-2 pt-1");
    expect(row.textContent).toContain("Übernehmen");
    expect(row.textContent).toContain("Verwerfen");
  });

  it("renders no wrapper and no actions row without them", () => {
    // The words sit directly in the live region — the shape every
    // existing caller's DOM has always been.
    const element = root({});
    expect(element.children).toHaveLength(0);
  });
});
