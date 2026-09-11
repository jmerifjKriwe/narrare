/**
 * ScratchpadPaneMode tests (NOTES-001 final-review blocker): the right-pane
 * decision must key note EXISTENCE off the unfiltered probe, never the
 * filtered list — filtered-zero shows the quiet prompt, only provable
 * emptiness (zero notes AND nothing filtered) shows the capture card, and
 * unknown existence renders neither.
 *
 * next-intl is mocked centrally (keys verbatim) so the prompt asserts its
 * key string.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { NoteFilters } from "../NoteFilterBar";
import { resolveScratchpadPaneMode, ScratchpadSelectPrompt } from "../ScratchpadPaneMode";

const noFilters: NoteFilters = { q: "", note_type: "", tag: "", scope: null };

const probe = (isSuccess: boolean, data: unknown[] | undefined) => ({ isSuccess, data });

describe("resolveScratchpadPaneMode", () => {
  it("returns unknown while the probe is pending or errored (no flash)", () => {
    expect(resolveScratchpadPaneMode(probe(false, undefined), noFilters)).toBe("unknown");
  });

  it("returns capture-card only at provable emptiness: zero notes, no filters", () => {
    expect(resolveScratchpadPaneMode(probe(true, []), noFilters)).toBe("capture-card");
  });

  it("returns select-prompt when notes exist", () => {
    expect(resolveScratchpadPaneMode(probe(true, [{ id: "n1" }]), noFilters)).toBe("select-prompt");
  });

  it.each([
    ["query", { ...noFilters, q: "aunt" }],
    ["type", { ...noFilters, note_type: "idea" }],
    ["tag", { ...noFilters, tag: "plot" }],
    ["scope", { ...noFilters, scope: { kind: "novel", id: "nv1" } }],
  ] as const)("returns select-prompt at zero notes with an active %s filter", (_, filters) => {
    expect(resolveScratchpadPaneMode(probe(true, []), filters)).toBe("select-prompt");
  });
});

describe("ScratchpadSelectPrompt", () => {
  it("renders the quiet select prompt", () => {
    render(<ScratchpadSelectPrompt />);
    expect(screen.getByTestId("scratchpad-select-prompt")).toHaveTextContent("empty.selectPrompt");
  });
});
