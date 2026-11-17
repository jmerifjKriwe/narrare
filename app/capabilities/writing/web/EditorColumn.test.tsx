// @vitest-environment jsdom
/**
 * The editor column (W4 Task 12, live): the scene-centric draft's paper
 * stage — the ribbon with the derived scene code, the honest disabled doors
 * and KACHEL 9's amber unsaved pill, the running head (book — author), the
 * written-out eyebrow, the overline, the EDITABLE drop-cap prose (a real
 * textbox), and the foot's live word count + the one save-status owner's
 * three faces (rest / saving / KACHEL 9's failure with Wiederholen). No
 * folio, no page count (row 9), no ghost text or prompt bar (PR 4). The
 * empty faces answer per the states sheet, their create doors disabled
 * until Task 13.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import type { Chapter, Novel, Scene } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { applyLocale } from "@shell/lib/locale";
import type { SaveStatus } from "@shell/lib/saveStatus";
import { countWords } from "@shell/lib/words";

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

const BODY = "Ich war gerade dabei, die Sensoren zu kalibrieren.\n\n»Quelle triangulieren«, befahl ich leise.";

function sceneRow(overrides: Partial<Scene> = {}): Scene {
  return {
    id: "s2",
    chapter_id: "c1",
    title: "Das Signal im Permafrost",
    body: BODY,
    setting: "Forschungsstation 7",
    story_time: "27. Oktober 2094, 03:14 UTC",
    position: 2,
    word_count: countWords(BODY),
    created_at: "2026-11-01T10:00:00Z",
    updated_at: "2026-11-14T09:30:00Z",
    ...overrides,
  };
}

function entryOf(scene: Scene = sceneRow(), chapter: Chapter = chapterRow()): SceneEntry {
  return { scene, chapter };
}

function renderColumn(
  props: {
    entry?: SceneEntry | null;
    emptyChapter?: boolean;
    status?: SaveStatus;
    novel?: Novel;
    onRetry?: () => void;
    onBodyChange?: (body: string) => void;
  } = {},
) {
  const onRetry = props.onRetry ?? vi.fn();
  const onBodyChange = props.onBodyChange ?? vi.fn();
  const utils = render(
    <EditorColumn
      novel={props.novel ?? novelRow()}
      entry={props.entry === undefined ? entryOf() : props.entry}
      emptyChapter={props.emptyChapter ?? false}
      status={props.status ?? "idle"}
      onRetry={onRetry}
      onBodyChange={onBodyChange}
    />,
  );
  return { ...utils, onRetry, onBodyChange };
}

beforeEach(() => {
  applyLocale("de");
  // TipTap's platform detection reads userAgent — the stub must carry it.
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"], userAgent: "jsdom" });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("the scene face", () => {
  it("the running head names the book and its author — the book alone when null", () => {
    const { rerender } = renderColumn();
    expect(screen.getByTestId("workspace-running-head").textContent).toBe("Dead Signal — H. Calder");
    rerender(
      <EditorColumn
        novel={novelRow({ author: null })}
        entry={entryOf()}
        emptyChapter={false}
        status="idle"
        onRetry={vi.fn()}
        onBodyChange={vi.fn()}
      />,
    );
    expect(screen.getByTestId("workspace-running-head").textContent).toBe("Dead Signal");
  });

  it("the eyebrow writes the chapter and scene ordinals out", () => {
    renderColumn();
    expect(screen.getByText("Kapitel Eins · Szene Zwei")).toBeTruthy();
  });

  it("the ordinals fall back to the digit beyond the bound", () => {
    renderColumn({ entry: entryOf(sceneRow({ position: 25 }), chapterRow({ position: 20 })) });
    expect(screen.getByText("Kapitel 21 · Szene 25")).toBeTruthy();
  });

  it("the scene title is the page's heading — the placeholder when untitled", () => {
    const { rerender } = renderColumn();
    expect(screen.getByRole("heading", { level: 1, name: "Das Signal im Permafrost" })).toBeTruthy();
    rerender(
      <EditorColumn
        novel={novelRow()}
        entry={entryOf(sceneRow({ title: "  " }))}
        emptyChapter={false}
        status="idle"
        onRetry={vi.fn()}
        onBodyChange={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("heading", { level: 1, name: de["writing.workspace.untitledScene"] }),
    ).toBeTruthy();
  });

  it("the overline carries setting and story_time when present — each alone, neither absent", () => {
    const { rerender } = renderColumn();
    expect(screen.getByText("Forschungsstation 7 · 27. Oktober 2094, 03:14 UTC")).toBeTruthy();
    rerender(
      <EditorColumn
        novel={novelRow()}
        entry={entryOf(sceneRow({ story_time: null }))}
        emptyChapter={false}
        status="idle"
        onRetry={vi.fn()}
        onBodyChange={vi.fn()}
      />,
    );
    expect(screen.getByText("Forschungsstation 7")).toBeTruthy();
  });

  it("the prose is an editable textbox rendering the body's paragraphs", async () => {
    renderColumn();
    const box = await screen.findByRole("textbox", { name: de["writing.workspace.editor.proseLabel"] });
    expect(box.getAttribute("aria-multiline")).toBe("true");
    await waitFor(() => expect(screen.getByRole("textbox").querySelectorAll("p")).toHaveLength(2));
    const paragraphs = screen.getByRole("textbox").querySelectorAll("p");
    expect(paragraphs[0].textContent).toBe("Ich war gerade dabei, die Sensoren zu kalibrieren.");
    expect(paragraphs[1].textContent).toBe("»Quelle triangulieren«, befahl ich leise.");
    // The live prose wears the drop-cap wrapper class (globals.css).
    expect(screen.getByRole("textbox").closest(".workspace-prose-live")).not.toBeNull();
  });

  it("an empty body keeps the paper honest — an empty editor, no invented prose", async () => {
    renderColumn({ entry: entryOf(sceneRow({ body: "  " })) });
    await screen.findByRole("textbox");
    await waitFor(() => expect(screen.getByRole("textbox").textContent).toBe(""));
  });

});

describe("the foot — one status owner, three faces", () => {
  it("at rest counts the scene's live words and reads Automatisch gesichert — no folio", async () => {
    renderColumn({ status: "idle" });
    expect(
      screen.getByText(de["writing.workspace.foot.words"].replace("{count, number}", String(countWords(BODY)))),
    ).toBeTruthy();
    expect(screen.getByText(de["writing.workspace.foot.saved"])).toBeTruthy();
    expect(screen.queryByText(/Seite/)).toBeNull();
    expect(screen.queryByText(/FOLIO/)).toBeNull();
  });

  it("the saved face reads the same as rest", () => {
    renderColumn({ status: "saved" });
    expect(screen.getByText(de["writing.workspace.foot.saved"])).toBeTruthy();
  });

  it("saving reads Sicherung läuft …", () => {
    renderColumn({ status: "saving" });
    expect(screen.getByText(de["writing.workspace.foot.saving"])).toBeTruthy();
    expect(screen.queryByText(de["writing.workspace.foot.saved"])).toBeNull();
  });

  it("failed is KACHEL 9's red face with a working Wiederholen", () => {
    const onRetry = vi.fn();
    renderColumn({ status: "failed", onRetry });
    expect(screen.getByText(de["writing.workspace.foot.failed"])).toBeTruthy();
    const retry = screen.getByRole("button", { name: de["writing.workspace.foot.retry"] });
    fireEvent.click(retry);
    expect(onRetry).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(de["writing.workspace.foot.saved"])).toBeNull();
  });
});

describe("the ribbon", () => {
  it("names the book, chapter and scene with the derived code badge", () => {
    renderColumn();
    const ribbon = screen.getByTestId("workspace-ribbon");
    expect(within(ribbon).getByText("Dead Signal")).toBeTruthy();
    expect(within(ribbon).getByText("Kapitel 1")).toBeTruthy();
    expect(within(ribbon).getByText("Szene 2")).toBeTruthy();
    expect(within(ribbon).getByText("K1-S2")).toBeTruthy();
  });

  it("the unsaved pill stands while saving or failed — not at rest", () => {
    const { rerender } = renderColumn({ status: "idle" });
    const ribbon = screen.getByTestId("workspace-ribbon");
    expect(within(ribbon).queryByText(de["writing.workspace.ribbon.unsaved"])).toBeNull();
    for (const status of ["saving", "failed", "saved"] as const) {
      rerender(
        <EditorColumn
          novel={novelRow()}
          entry={entryOf()}
          emptyChapter={false}
          status={status}
          onRetry={vi.fn()}
          onBodyChange={vi.fn()}
        />,
      );
      const present = within(screen.getByTestId("workspace-ribbon")).queryByText(
        de["writing.workspace.ribbon.unsaved"],
      );
      if (status === "saved") expect(present).toBeNull();
      else expect(present).not.toBeNull();
    }
  });

  it("the chapter-target pill keeps the neutral — the read carries no chapter goal yet (Task 19)", () => {
    renderColumn();
    const ribbon = screen.getByTestId("workspace-ribbon");
    expect(within(ribbon).getByText(de["writing.workspace.ribbon.chapterTarget"])).toBeTruthy();
    expect(within(ribbon).getByRole("button", { name: de["writing.workspace.ribbon.targetEdit"] }).hasAttribute("disabled")).toBe(true);
  });

  it("focus, history and export stay honestly disabled with their notes", () => {
    renderColumn();
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
    renderColumn({ entry: null });
    expect(
      screen.getByRole("heading", { level: 1, name: de["writing.workspace.emptyBook.editorTitle"] }),
    ).toBeTruthy();
    expect(screen.getByText(de["writing.workspace.emptyBook.editorBody"])).toBeTruthy();
    expect(screen.queryByTestId("workspace-ribbon")).toBeNull();
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("the empty chapter explains the scene and disables the create door", () => {
    renderColumn({ entry: null, emptyChapter: true });
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
