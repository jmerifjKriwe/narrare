// @vitest-environment jsdom
/**
 * The editor column (W4 Task 11, read-only): the scene-centric draft's
 * paper stage on the shell's tokens — the ribbon with the derived scene
 * code and the honest disabled doors, the running head (book — author,
 * book alone when null), the written-out chapter/scene eyebrow, the
 * setting/story_time overline when present, the drop-cap prose and the
 * foot's word count + interim autosave line. No folio, no page count
 * (row 9), no ghost text or prompt bar (PR 4). The empty faces answer per
 * the states sheet: the unwritten work and the first-scene invitation,
 * their create doors disabled until Task 13.
 */
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import type { Chapter, Novel, Scene } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { applyLocale } from "@shell/lib/locale";

import { EditorColumn } from "./EditorColumn";
import type { SceneEntry } from "./workspace";

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

function chapterRow(overrides: Partial<Chapter> = {}): Chapter {
  return {
    id: "c1",
    novel_id: "11111111-1111-1111-1111-111111111111",
    title: "Ghost in the Machine",
    position: 0,
    scene_count: 2,
    word_count: 765,
    created_at: "2026-11-01T10:00:00Z",
    updated_at: "2026-11-10T10:00:00Z",
    ...overrides,
  };
}

function sceneRow(overrides: Partial<Scene> = {}): Scene {
  return {
    id: "s2",
    chapter_id: "c1",
    title: "Das Signal im Permafrost",
    body: "Ich war gerade dabei, die Sensoren zu kalibrieren.\n\n»Quelle triangulieren«, befahl ich leise.",
    setting: "Forschungsstation 7",
    story_time: "27. Oktober 2094, 03:14 UTC",
    position: 2,
    word_count: 423,
    created_at: "2026-11-01T10:00:00Z",
    updated_at: "2026-11-14T09:30:00Z",
    ...overrides,
  };
}

function entryOf(scene: Scene = sceneRow(), chapter: Chapter = chapterRow()): SceneEntry {
  return { scene, chapter };
}

beforeEach(() => {
  applyLocale("de");
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("the scene face", () => {
  it("the running head names the book and its author — the book alone when null", () => {
    const { rerender } = render(<EditorColumn novel={novelRow()} entry={entryOf()} emptyChapter={false} />);
    expect(screen.getByTestId("workspace-running-head").textContent).toBe("Dead Signal — H. Calder");
    rerender(<EditorColumn novel={novelRow({ author: null })} entry={entryOf()} emptyChapter={false} />);
    expect(screen.getByTestId("workspace-running-head").textContent).toBe("Dead Signal");
  });

  it("the eyebrow writes the chapter and scene ordinals out", () => {
    render(<EditorColumn novel={novelRow()} entry={entryOf()} emptyChapter={false} />);
    expect(screen.getByText("Kapitel Eins · Szene Zwei")).toBeTruthy();
  });

  it("the ordinals fall back to the digit beyond the bound", () => {
    const chapter = chapterRow({ position: 20 });
    const scene = sceneRow({ position: 25 });
    render(<EditorColumn novel={novelRow()} entry={entryOf(scene, chapter)} emptyChapter={false} />);
    expect(screen.getByText("Kapitel 21 · Szene 25")).toBeTruthy();
  });

  it("the scene title is the page's heading — the placeholder when untitled", () => {
    const { rerender } = render(<EditorColumn novel={novelRow()} entry={entryOf()} emptyChapter={false} />);
    expect(screen.getByRole("heading", { level: 1, name: "Das Signal im Permafrost" })).toBeTruthy();
    rerender(<EditorColumn novel={novelRow()} entry={entryOf(sceneRow({ title: "  " }))} emptyChapter={false} />);
    expect(
      screen.getByRole("heading", { level: 1, name: de["writing.workspace.untitledScene"] }),
    ).toBeTruthy();
  });

  it("the overline carries setting and story_time when present — each alone, neither absent", () => {
    const { rerender } = render(<EditorColumn novel={novelRow()} entry={entryOf()} emptyChapter={false} />);
    expect(screen.getByText("Forschungsstation 7 · 27. Oktober 2094, 03:14 UTC")).toBeTruthy();
    rerender(
      <EditorColumn novel={novelRow()} entry={entryOf(sceneRow({ story_time: null }))} emptyChapter={false} />,
    );
    expect(screen.getByText("Forschungsstation 7")).toBeTruthy();
    rerender(
      <EditorColumn
        novel={novelRow()}
        entry={entryOf(sceneRow({ setting: null, story_time: null }))}
        emptyChapter={false}
      />,
    );
    expect(screen.queryByText("Forschungsstation 7")).toBeNull();
  });

  it("the prose renders the body's paragraphs, the first with the drop cap", () => {
    render(<EditorColumn novel={novelRow()} entry={entryOf()} emptyChapter={false} />);
    const prose = screen.getByTestId("workspace-prose");
    const paragraphs = prose.querySelectorAll("p");
    expect(paragraphs).toHaveLength(2);
    expect(paragraphs[0].textContent).toBe("Ich war gerade dabei, die Sensoren zu kalibrieren.");
    expect(paragraphs[0].className).toContain("workspace-drop-cap");
    expect(paragraphs[1].textContent).toBe("»Quelle triangulieren«, befahl ich leise.");
    expect(paragraphs[1].className).not.toContain("workspace-drop-cap");
  });

  it("an empty body keeps the paper honest — no paragraphs, no invented prose", () => {
    render(<EditorColumn novel={novelRow()} entry={entryOf(sceneRow({ body: "  " }))} emptyChapter={false} />);
    expect(screen.getByTestId("workspace-prose").querySelectorAll("p")).toHaveLength(0);
  });

  it("the foot counts the scene's own words and carries the interim autosave line — no folio", () => {
    render(<EditorColumn novel={novelRow()} entry={entryOf()} emptyChapter={false} />);
    expect(screen.getByText("423 Wörter im Gesamtabschnitt")).toBeTruthy();
    expect(screen.getByText(de["writing.workspace.foot.saved"])).toBeTruthy();
    expect(screen.queryByText(/Seite/)).toBeNull();
    expect(screen.queryByText(/FOLIO/)).toBeNull();
  });

  it("the ribbon names the book, chapter and scene with the derived code badge", () => {
    render(<EditorColumn novel={novelRow()} entry={entryOf()} emptyChapter={false} />);
    const ribbon = screen.getByTestId("workspace-ribbon");
    expect(within(ribbon).getByText("Dead Signal")).toBeTruthy();
    expect(within(ribbon).getByText("Kapitel 1")).toBeTruthy();
    expect(within(ribbon).getByText("Szene 2")).toBeTruthy();
    expect(within(ribbon).getByText("K1-S2")).toBeTruthy();
  });

  it("the chapter-target pill keeps the neutral — the read carries no chapter goal yet (Task 19)", () => {
    render(<EditorColumn novel={novelRow()} entry={entryOf()} emptyChapter={false} />);
    const ribbon = screen.getByTestId("workspace-ribbon");
    expect(within(ribbon).getByText(de["writing.workspace.ribbon.chapterTarget"])).toBeTruthy();
    expect(within(ribbon).getByRole("button", { name: de["writing.workspace.ribbon.targetEdit"] }).hasAttribute("disabled")).toBe(true);
  });

  it("focus, history and export stay honestly disabled with their notes", () => {
    render(<EditorColumn novel={novelRow()} entry={entryOf()} emptyChapter={false} />);
    const ribbon = screen.getByTestId("workspace-ribbon");
    for (const [name, note] of [
      [de["writing.workspace.ribbon.focus"], de["writing.workspace.ribbon.focusNote"]],
      [de["writing.workspace.ribbon.history"], de["writing.workspace.ribbon.historyNote"]],
      [de["writing.workspace.ribbon.export"], de["writing.workspace.ribbon.exportNote"]],
    ] as const) {
      const button = within(ribbon).getByRole("button", { name });
      expect(button.hasAttribute("disabled")).toBe(true);
      expect(button.getAttribute("title")).toBe(note);
    }
  });
});

describe("the empty faces", () => {
  it("the empty book invites the first chapter — the door disabled until Task 13", () => {
    render(<EditorColumn novel={novelRow()} entry={null} emptyChapter={false} />);
    expect(
      screen.getByRole("heading", { level: 1, name: de["writing.workspace.emptyBook.editorTitle"] }),
    ).toBeTruthy();
    expect(screen.getByText(de["writing.workspace.emptyBook.editorBody"])).toBeTruthy();
    expect(screen.queryByTestId("workspace-ribbon")).toBeNull();
  });

  it("the empty chapter explains the scene and disables the create door", () => {
    render(<EditorColumn novel={novelRow()} entry={null} emptyChapter={true} />);
    expect(
      screen.getByRole("heading", { level: 1, name: de["writing.workspace.emptyChapter.title"] }),
    ).toBeTruthy();
    expect(screen.getByText(de["writing.workspace.emptyChapter.body"])).toBeTruthy();
    const button = screen.getByRole("button", { name: de["writing.workspace.emptyChapter.action"] });
    expect(button.hasAttribute("disabled")).toBe(true);
    expect(button.getAttribute("title")).toBe(de["writing.workspace.crudNote"]);
    expect(screen.queryByTestId("workspace-ribbon")).toBeNull();
  });
});
