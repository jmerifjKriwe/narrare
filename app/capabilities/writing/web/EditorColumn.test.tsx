// @vitest-environment jsdom
/**
 * The editor column (W4 Task 12, live): the scene-centric draft's paper
 * stage — the ribbon with the derived scene code, the honest disabled doors
 * and KACHEL 9's amber unsaved pill, the running head (book — author), the
 * written-out eyebrow, the overline, the EDITABLE drop-cap prose (a real
 * textbox), and the foot's live word count + the one save-status owner's
 * three faces (rest / saving / KACHEL 9's failure with Wiederholen). No
 * folio, no page count (row 9). The ghost text and the prompt bar are LIVE
 * (Task 16): the bar floats over the scene face alone, and a prose edit
 * dismisses the standing ghost (the page's wiring, proven here at the
 * column's door). The empty faces answer per the states sheet; Kachel 4's
 * first-scene door is LIVE (Task 13) — the canonical new-chapter
 * experience (D16).
 */
import { cleanup, configure, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

// Full-suite load: see WorkspacePage.test.tsx.
configure({ asyncUtilTimeout: 5000 });
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import type { Chapter, Novel, Scene } from "@shell/lib/api/client";
import { applyLocale } from "@shell/lib/locale";
import type { SaveStatus } from "@shell/lib/saveStatus";
import { countWords } from "@shell/lib/words";
import { de, merged } from "@shell/lib/test/catalogs";

import { EditorColumn } from "./EditorColumn";
import type { Continuation, SceneEntry } from "./workspace";

// The ribbon's history and export doors name their state, not a future
// release (#979).
const STATUS_NOTE = {
  en: "Not available yet.",
  de: "Noch nicht verfügbar.",
  fr: "Pas encore disponible.",
} as const;

const FUTURE_PROMISE =
  /build-out|aufbau|wave|welle|vague|appear|erschein|appara|coming soon|kommt mit|arrive avec|future|becomes available|later/i;

describe("the ribbon's disabled notes speak to the reader", () => {
  it("are status-only in every catalog, never a future promise", () => {
    for (const locale of ["en", "de", "fr"] as const) {
      for (const key of [
        "writing.workspace.ribbon.historyNote",
        "writing.workspace.ribbon.exportNote",
      ] as const) {
        const note = merged[locale][key];
        expect(note).toBe(STATUS_NOTE[locale]);
        expect(note).not.toMatch(FUTURE_PROMISE);
      }
    }
  });
});

// jsdom lays out nothing: ProseMirror reads Range rects when it scrolls a
// selection into view (the typing leg focuses the live editor). Hand it the
// zeros the elements claim (the page test's own polyfill).
const zeroRect = { top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0, x: 0, y: 0 } as DOMRect;
Range.prototype.getClientRects = function (): DOMRectList {
  return [zeroRect] as unknown as DOMRectList;
};
Range.prototype.getBoundingClientRect = () => zeroRect;

/** The continuation at rest — the column's tests drive the faces, the
 *  hook's own lifecycle lives in the workspace seam's tests. */
function continuationOf(overrides: Partial<Continuation> = {}): Continuation {
  return {
    phase: "idle",
    text: "",
    errorCode: null,
    start: vi.fn(),
    dismiss: vi.fn(),
    retry: vi.fn(),
    ...overrides,
  };
}

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
    target_words: null,
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
    onCreateScene?: () => void;
    onEnterZen?: () => void;
    onEditTarget?: () => void;
    continuation?: Continuation;
    zenBusy?: boolean;
  } = {},
) {
  const onRetry = props.onRetry ?? vi.fn();
  const onBodyChange = props.onBodyChange ?? vi.fn();
  const onCreateScene = props.onCreateScene ?? vi.fn();
  const onEnterZen = props.onEnterZen ?? vi.fn();
  const onEditTarget = props.onEditTarget ?? vi.fn();
  const utils = render(
    <EditorColumn
      novel={props.novel ?? novelRow()}
      entry={props.entry === undefined ? entryOf() : props.entry}
      emptyChapter={props.emptyChapter ?? false}
      status={props.status ?? "idle"}
      onRetry={onRetry}
      onBodyChange={onBodyChange}
      onCreateScene={onCreateScene}
      onEnterZen={onEnterZen}
      onEditTarget={onEditTarget}
      continuation={props.continuation ?? continuationOf()}
      zenBusy={props.zenBusy ?? false}
    />,
  );
  return { ...utils, onRetry, onBodyChange, onCreateScene, onEnterZen, onEditTarget };
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
        onCreateScene={vi.fn()}
        onEnterZen={vi.fn()}
        onEditTarget={vi.fn()}
        zenBusy={false}
        continuation={continuationOf()}
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
        onCreateScene={vi.fn()}
        onEnterZen={vi.fn()}
        onEditTarget={vi.fn()}
        zenBusy={false}
        continuation={continuationOf()}
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
        onCreateScene={vi.fn()}
        onEnterZen={vi.fn()}
        onEditTarget={vi.fn()}
        zenBusy={false}
        continuation={continuationOf()}
      />,
    );
    expect(screen.getByText("Forschungsstation 7")).toBeTruthy();
    rerender(
      <EditorColumn
        novel={novelRow()}
        entry={entryOf(sceneRow({ setting: null }))}
        emptyChapter={false}
        status="idle"
        onRetry={vi.fn()}
        onBodyChange={vi.fn()}
        onCreateScene={vi.fn()}
        onEnterZen={vi.fn()}
        onEditTarget={vi.fn()}
        zenBusy={false}
        continuation={continuationOf()}
      />,
    );
    expect(screen.getByText("27. Oktober 2094, 03:14 UTC")).toBeTruthy();
    // The neither leg: both labels unset, the overline is absent — no empty
    // line, no stray separator (the name's claim, made true again).
    rerender(
      <EditorColumn
        novel={novelRow()}
        entry={entryOf(sceneRow({ setting: null, story_time: null }))}
        emptyChapter={false}
        status="idle"
        onRetry={vi.fn()}
        onBodyChange={vi.fn()}
        onCreateScene={vi.fn()}
        onEnterZen={vi.fn()}
        onEditTarget={vi.fn()}
        zenBusy={false}
        continuation={continuationOf()}
      />,
    );
    expect(screen.queryByTestId("workspace-overline")).toBeNull();
  });

  it("the prose is an editable textbox rendering the body's paragraphs", async () => {
    renderColumn();
    const box = await screen.findByRole("textbox", { name: de["writing.workspace.editor.proseLabel"] });
    expect(box.getAttribute("aria-multiline")).toBe("true");
    await waitFor(() => expect(box.querySelectorAll("p")).toHaveLength(2));
    const paragraphs = box.querySelectorAll("p");
    expect(paragraphs[0].textContent).toBe("Ich war gerade dabei, die Sensoren zu kalibrieren.");
    expect(paragraphs[1].textContent).toBe("»Quelle triangulieren«, befahl ich leise.");
    // The live prose wears the drop-cap wrapper class (globals.css).
    expect(box.closest(".workspace-prose-live")).not.toBeNull();
  });

  it("an empty body keeps the paper honest — an empty editor, no invented prose", async () => {
    renderColumn({ entry: entryOf(sceneRow({ body: "  " })) });
    const box = await screen.findByRole("textbox", { name: de["writing.workspace.editor.proseLabel"] });
    await waitFor(() => expect(box.textContent).toBe(""));
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
          onCreateScene={vi.fn()}
          onEnterZen={vi.fn()}
          onEditTarget={vi.fn()}
          zenBusy={false}
          continuation={continuationOf()}
        />,
      );
      const present = within(screen.getByTestId("workspace-ribbon")).queryByText(
        de["writing.workspace.ribbon.unsaved"],
      );
      if (status === "saved") expect(present).toBeNull();
      else expect(present).not.toBeNull();
    }
  });

  it("the chapter-target pill keeps the neutral when no goal stands — the setter ready (Task 19)", () => {
    const { onEditTarget } = renderColumn();
    const ribbon = screen.getByTestId("workspace-ribbon");
    expect(within(ribbon).getByText(de["writing.workspace.ribbon.chapterTarget"])).toBeTruthy();
    const edit = within(ribbon).getByRole("button", { name: de["writing.workspace.ribbon.targetEdit"] });
    expect(edit.hasAttribute("disabled")).toBe(false);
    fireEvent.click(edit);
    expect(onEditTarget).toHaveBeenCalledTimes(1);
  });

  it("a set chapter goal reads the real pair and fills the track (D8/D20, Task 19)", () => {
    renderColumn({ entry: entryOf(sceneRow(), chapterRow({ target_words: 1000, word_count: 765 })) });
    const ribbon = screen.getByTestId("workspace-ribbon");
    expect(
      within(ribbon).getByText(
        de["writing.workspace.ribbon.targetValue"].replace("{count, number}", "765").replace("{target, number}", "1.000"),
      ),
    ).toBeTruthy();
    const fill = ribbon.querySelector("[data-chapter-target-fill]");
    expect(fill?.getAttribute("style")).toContain("76.5%");
  });

  it("history and export stay honestly disabled with their notes", () => {
    renderColumn();
    const ribbon = screen.getByTestId("workspace-ribbon");
    for (const [name, note] of [
      [de["writing.workspace.ribbon.history"], de["writing.workspace.ribbon.historyNote"]],
      [de["writing.workspace.ribbon.export"], de["writing.workspace.ribbon.exportNote"]],
    ] as const) {
      const button = within(ribbon).getByRole("button", { name });
      expect(button.hasAttribute("disabled")).toBe(true);
      expect(button.getAttribute("title")).toBe(note);
    }
  });

  it("the Fokus door is LIVE (Task 18) — it opens zen, the interim note is gone", () => {
    const { onEnterZen } = renderColumn();
    const ribbon = screen.getByTestId("workspace-ribbon");
    const door = within(ribbon).getByRole("button", { name: de["writing.workspace.ribbon.focus"] });
    expect(door.hasAttribute("disabled")).toBe(false);
    expect(door.getAttribute("title")).toBeNull();
    fireEvent.click(door);
    expect(onEnterZen).toHaveBeenCalledTimes(1);
  });

  it("a busy zen transition holds the Fokus door and locks the prose — the family's busy face", async () => {
    const { onEnterZen } = renderColumn({ zenBusy: true });
    const ribbon = screen.getByTestId("workspace-ribbon");
    // The door wears the family's busy face: the busy label, disabled.
    const door = within(ribbon).getByRole("button", { name: de["writing.workspace.ribbon.focusBusy"] });
    expect(door.hasAttribute("disabled")).toBe(true);
    fireEvent.click(door);
    expect(onEnterZen).not.toHaveBeenCalled();
    // The live prose is locked — keystrokes in the swap window would die
    // with the unmount (the refetched body predates them).
    const box = await screen.findByRole("textbox", { name: de["writing.workspace.editor.proseLabel"] });
    await waitFor(() => expect(box.getAttribute("contenteditable")).toBe("false"));
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

  it("the empty chapter explains the scene — the first-scene door live (D16's canonical new chapter)", () => {
    const { onCreateScene } = renderColumn({ entry: null, emptyChapter: true });
    expect(
      screen.getByRole("heading", { level: 1, name: de["writing.workspace.emptyChapter.title"] }),
    ).toBeTruthy();
    expect(screen.getByText(de["writing.workspace.emptyChapter.body"])).toBeTruthy();
    const button = screen.getByRole("button", { name: de["writing.workspace.emptyChapter.action"] });
    expect(button.hasAttribute("disabled")).toBe(false);
    fireEvent.click(button);
    expect(onCreateScene).toHaveBeenCalledTimes(1);
    expect(screen.queryByTestId("workspace-ribbon")).toBeNull();
  });
});

describe("the prompt bar and the ghost (Task 16)", () => {
  it("the bar floats on the scene face — input, primary and the three pills", async () => {
    renderColumn();
    await screen.findByRole("textbox", { name: de["writing.workspace.editor.proseLabel"] });
    expect(
      screen.getByRole("textbox", { name: de["writing.workspace.promptBar.inputLabel"] }),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: de["writing.workspace.promptBar.continue"] }),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: de["writing.workspace.promptBar.pillTension"] }),
    ).toBeTruthy();
  });

  it("the empty faces carry no bar — no scene, nothing to continue", () => {
    renderColumn({ entry: null });
    expect(
      screen.queryByRole("textbox", { name: de["writing.workspace.promptBar.inputLabel"] }),
    ).toBeNull();
    renderColumn({ entry: null, emptyChapter: true });
    expect(
      screen.queryByRole("button", { name: de["writing.workspace.promptBar.continue"] }),
    ).toBeNull();
  });

  it("a prose edit rides the onChange door with the whole body — the page wires the dismissal", async () => {
    const continuation = continuationOf({ phase: "pending", text: "Der Nebel hob sich." });
    const onBodyChange = vi.fn();
    renderColumn({ continuation, onBodyChange });
    const box = await screen.findByRole("textbox", { name: de["writing.workspace.editor.proseLabel"] });
    await waitFor(() => expect(box.textContent).toContain("Ich war gerade dabei"));
    expect(screen.getByTestId("ghost-preview")).toBeTruthy();
    // A real keystroke through TipTap — the onChange door the page wires
    // (the dismissal itself is the page's wrapper, proven in its own test).
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    box.focus();
    await user.keyboard("X");
    await waitFor(() => expect(onBodyChange).toHaveBeenCalled());
    expect(onBodyChange.mock.calls[0][0]).toContain("Ich war gerade dabei");
    expect(onBodyChange.mock.calls[0][0]).toContain("X");
  });

  it("the streaming ghost renders at the tail with the ARIA chip", async () => {
    renderColumn({
      continuation: continuationOf({ phase: "streaming", text: "Der Nebel hob sich " }),
    });
    await screen.findByRole("textbox", { name: de["writing.workspace.editor.proseLabel"] });
    expect(screen.getByTestId("ghost-preview").textContent).toContain("Der Nebel hob sich ");
    expect(screen.getByText(de["writing.workspace.ghost.writing"])).toBeTruthy();
    // KACHEL 7's busy bar stands in for the input row.
    expect(screen.getByText(de["writing.workspace.promptBar.busy"])).toBeTruthy();
    expect(screen.getByRole("button", { name: de["writing.workspace.promptBar.stop"] })).toBeTruthy();
  });
});
