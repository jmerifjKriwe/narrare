/**
 * Notice's class contract, pinned whole per tone: this helper is the app's
 * only error/empty/loading vocabulary — the census (P18) demands
 * `text-danger` = 0 outside this file — so a tone losing its colour, or a
 * fill sneaking under it, fails here, not in a screenshot. The quiet
 * tone's `text-muted` is legal on every surface a Notice rides (card,
 * panel, ground); what no tone may wear is a `--soft` fill (muted on soft
 * is below AA — the parked P1 rule), which is why the no-fill law is
 * pinned beside the strings. Behaviour (the live region, the axe pass) is
 * the E2E suites' job.
 */
import { describe, expect, it } from "vitest";

import { NOTICE_TONES, noticeClass } from "./Notice";

const MATRIX: Record<(typeof NOTICE_TONES)[number], string> = {
  info: "flex items-center gap-2 px-3 py-2 text-body text-foreground",
  warning: "flex items-center gap-2 px-3 py-2 text-body text-warning",
  danger: "flex items-center gap-2 px-3 py-2 text-body text-danger",
  quiet: "flex items-center gap-2 px-3 py-2 text-body text-muted",
};

describe("noticeClass", () => {
  it("carries exactly the pinned string in every tone", () => {
    for (const tone of NOTICE_TONES) {
      expect(noticeClass(tone)).toBe(MATRIX[tone]);
    }
  });

  it("speaks the state colours: danger wears the danger token, quiet is the muted voice", () => {
    expect(noticeClass("danger")).toContain("text-danger");
    expect(noticeClass("danger")).not.toContain("border");
    expect(noticeClass("quiet")).toContain("text-muted");
  });

  it("never wears the legacy vocabulary, a primary fill or any fill at all", () => {
    for (const tone of NOTICE_TONES) {
      const classes = noticeClass(tone);
      expect(classes).not.toContain("text-sm");
      expect(classes).not.toContain("rounded-md");
      expect(classes).not.toContain("bg-primary");
      // The no-fill law: the notice's quiet form has no surface of its
      // own — no `--soft` (muted on soft is below AA), no card, no panel.
      expect(classes).not.toContain("bg-");
    }
  });
});
