// @vitest-environment jsdom
/**
 * The inspector dock (W4 Task 11): the scene-centric draft's round geometry
 * with honest neutrals — the finding card (INTERIM #866), the entity
 * spotlight (#867), the atmosphere grid (#868), the disabled ⌘J chip
 * (#869) and layout tune (#881) — and the ONE real card: the cover
 * miniature with the book's own target, count and derived progress.
 * The draft's mock figures (85.000 / 3.384 / 4 %) never ship as data.
 */
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import type { Novel } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { applyLocale } from "@shell/lib/locale";

import { InspectorDock } from "./InspectorDock";

const de = catalogs.de;

function novelRow(overrides: Partial<Novel> = {}): Novel {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    title: "Dead Signal",
    genre: "Science Fiction",
    blurb: null,
    author: "H. Calder",
    language: null,
    chapter_count: 2,
    word_count: 1855,
    created_at: "2026-11-01T10:00:00Z",
    updated_at: "2026-11-14T10:00:00Z",
    last_exported_at: null,
    status: "draft",
    series_title: null,
    series_volume: null,
    archived_at: null,
    target_words: 85000,
    ...overrides,
  };
}

beforeEach(() => {
  applyLocale("de");
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("the dock's neutral geometry", () => {
  it("the header names the consistency checker with the neutral badge", () => {
    render(<InspectorDock novel={novelRow()} />);
    expect(screen.getByRole("heading", { name: de["writing.workspace.dock.title"] })).toBeTruthy();
  });

  it("the finding card stays neutral until the knowledge wave (#866)", () => {
    render(<InspectorDock novel={novelRow()} />);
    const card = screen.getByTestId("dock-finding");
    expect(within(card).getByText(de["writing.workspace.dock.finding"])).toBeTruthy();
    expect(within(card).getByText(de["writing.workspace.dock.findingEmpty"])).toBeTruthy();
    expect(within(card).getByText(de["writing.workspace.dock.findingNote"])).toBeTruthy();
    expect(card.className).toContain("border-dashed");
  });

  it("the entity spotlight keeps its neutral fields and the disabled wiki door (#867)", () => {
    render(<InspectorDock novel={novelRow()} />);
    const card = screen.getByTestId("dock-entity");
    for (const key of [
      "writing.workspace.dock.entityName",
      "writing.workspace.dock.entityFirst",
      "writing.workspace.dock.entityBinding",
    ] as const) {
      expect(within(card).getByText(de[key])).toBeTruthy();
    }
    const wiki = within(card).getByRole("button", { name: de["writing.workspace.dock.wiki"] });
    expect(wiki.hasAttribute("disabled")).toBe(true);
  });

  it("the atmosphere grid keeps its neutral values — no mock scene label (#868)", () => {
    render(<InspectorDock novel={novelRow()} />);
    const card = screen.getByTestId("dock-atmosphere");
    expect(within(card).getByText(de["writing.workspace.dock.light"])).toBeTruthy();
    expect(within(card).getByText(de["writing.workspace.dock.acoustics"])).toBeTruthy();
    expect(screen.queryByText("Permafrost Station 7")).toBeNull();
  });

  it("the foot's ⌘J chip and layout tune stay disabled with their marks (#869, #881)", () => {
    render(<InspectorDock novel={novelRow()} />);
    const foot = screen.getByTestId("dock-foot");
    const assistant = within(foot).getByText(de["writing.workspace.dock.assistant"]);
    expect(assistant.closest("[aria-disabled='true']")).not.toBeNull();
    expect(within(foot).getByText(de["writing.workspace.dock.soon"])).toBeTruthy();
    const layout = within(foot).getByRole("button", { name: de["writing.workspace.dock.layout"] });
    expect(layout.hasAttribute("disabled")).toBe(true);
    expect(layout.getAttribute("title")).toContain(de["writing.workspace.dock.layoutNote"]);
  });
});

describe("the cover miniature — the dock's one real card", () => {
  it("renders the cover system's miniature with the book's own figures", () => {
    render(<InspectorDock novel={novelRow()} />);
    const card = screen.getByTestId("dock-cover");
    // The cover system's monogram — the real object, never the draft's chip.
    expect(within(card).getByText("DS")).toBeTruthy();
    expect(within(card).getByText("Dead Signal")).toBeTruthy();
    expect(within(card).getByText(/85\.000/)).toBeTruthy();
    expect(within(card).getByText(/1\.855/)).toBeTruthy();
    // 1855 / 85000 = 2.18 % — floored, the shelf's own rule.
    expect(within(card).getByText("2 % Gesamt")).toBeTruthy();
  });

  it("a missing target keeps the honest neutral — no percent, empty track", () => {
    render(<InspectorDock novel={novelRow({ target_words: null })} />);
    const card = screen.getByTestId("dock-cover");
    expect(within(card).queryByText(/Gesamt/)).toBeNull();
    expect(within(card).getByText(/1\.855/)).toBeTruthy();
  });

  it("the progress never overflows the track — a finished book reads 100", () => {
    render(<InspectorDock novel={novelRow({ word_count: 90000 })} />);
    const card = screen.getByTestId("dock-cover");
    expect(within(card).getByText("100 % Gesamt")).toBeTruthy();
  });
});
