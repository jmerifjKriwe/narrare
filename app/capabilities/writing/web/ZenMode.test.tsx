// @vitest-environment jsdom
/**
 * The zen mode (W4 Task 18) — the round's zen-focus-2 authority on the
 * shell's tokens: the centered scene prose under the manuscript head, the
 * Absatz-/Satz-/Normal dimming (frontend-real, D6), the session-only
 * pomodoro, the real counters (today from the activity aggregate, session
 * from the live delta), the soundscape disabled with its gap note (row 12),
 * NO sepia control (D18), and the ghost reachable inside the room — the
 * prompt bar asks, the pending preview stands at the tail, Tab accepts
 * into the one write path. The page owns F9/Esc (D19); here the surface
 * itself: its anatomy, its controls, its focus trap.
 */
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import type { Chapter, Novel, Scene } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { applyLocale } from "@shell/lib/locale";

import { ZenMode } from "./ZenMode";
import type { Continuation, SceneEntry } from "./workspace";

const de = catalogs.de;

// jsdom lays out nothing: ProseMirror reads Range rects when it scrolls a
// selection into view (the zen entry focuses the prose tail). Hand it the
// zeros the elements claim (the page test's own polyfill).
const zeroRect = { top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0, x: 0, y: 0 } as DOMRect;
Range.prototype.getClientRects = function (): DOMRectList {
  return [zeroRect] as unknown as DOMRectList;
};
Range.prototype.getBoundingClientRect = () => zeroRect;

const NOVEL: Novel = {
  id: "11111111-1111-1111-1111-111111111111",
  title: "Dead Signal",
  genre: "Hard Sci-Fi / Mystery",
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
};

const CHAPTER: Chapter = {
  id: "c2",
  novel_id: NOVEL.id,
  title: "Nevada Echoes",
  position: 1,
  scene_count: 1,
  target_words: null,
  word_count: 1090,
  created_at: "2026-11-01T10:00:00Z",
  updated_at: "2026-11-11T10:00:00Z",
};

const BODY = "Erster Absatz mit Text.\n\nZweiter Absatz folgt hier.\n\nDritter Absatz schließt ab.";

const SCENE: Scene = {
  id: "s21",
  chapter_id: "c2",
  title: "Sub-Basement",
  body: BODY,
  setting: "Sub-Basement Nevada Test Site",
  story_time: "27. Oktober 2094, 03:14 UTC",
  position: 1,
  word_count: 15,
  created_at: "2026-11-01T10:00:00Z",
  updated_at: "2026-11-12T07:00:00Z",
};

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

function renderZen(
  props: {
    entry?: SceneEntry;
    todayWords?: number | null;
    continuation?: Continuation;
    onBodyChange?: (body: string) => void;
    onExit?: () => void;
    zenBusy?: boolean;
  } = {},
) {
  const onBodyChange = props.onBodyChange ?? vi.fn();
  const onExit = props.onExit ?? vi.fn();
  const continuation = props.continuation ?? continuationOf();
  render(
    <ZenMode
      novel={NOVEL}
      entry={props.entry ?? { scene: SCENE, chapter: CHAPTER }}
      todayWords={props.todayWords === undefined ? 412 : props.todayWords}
      continuation={continuation}
      onBodyChange={onBodyChange}
      onExit={onExit}
      zenBusy={props.zenBusy ?? false}
    />,
  );
  return { onBodyChange, onExit, continuation };
}

beforeEach(() => {
  applyLocale("de");
  // TipTap's platform detection reads userAgent — the stub must carry it.
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"], userAgent: "jsdom" });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("the zen anatomy — the round's zen-focus-2 authority", () => {
  it("the manuscript head: the book eyebrow, the chapter title, the scene overline, the fokus divider", async () => {
    renderZen();
    const room = screen.getByRole("dialog", { name: de["writing.workspace.zen.label"] });
    expect(within(room).getByText(de["writing.workspace.zen.eyebrow"].replace("{title}", "Dead Signal"))).toBeTruthy();
    expect(
      within(room).getByRole("heading", { level: 1, name: "Kapitel 2 — Nevada Echoes" }),
    ).toBeTruthy();
    // The scene overline is the row's own setting · story_time (the
    // workspace overline's rule), never the draft's mock line.
    expect(
      within(room).getByText("Sub-Basement Nevada Test Site · 27. Oktober 2094, 03:14 UTC"),
    ).toBeTruthy();
    expect(within(room).getByText(de["writing.workspace.zen.focusDivider"])).toBeTruthy();
    // The exit chip names the way back and the key that takes it (D19).
    const exit = within(room).getByRole("button", { name: de["writing.workspace.zen.exit"] });
    expect(within(exit).getByText("Esc")).toBeTruthy();
    // The decorative spines and the end mark stand, aria-hidden.
    expect(room.querySelectorAll("aside[aria-hidden='true']")).toHaveLength(2);
    expect(within(room).getByText("§ § §")).toBeTruthy();
    // The prose is the scene's own, live and labelled.
    const box = await screen.findByRole("textbox", { name: de["writing.workspace.editor.proseLabel"] });
    await waitFor(() => expect(box.textContent).toContain("Dritter Absatz schließt ab."));
  });

  it("an unset overline keeps the head honest — no invented line", async () => {
    renderZen({ entry: { scene: { ...SCENE, setting: null, story_time: null }, chapter: CHAPTER } });
    await screen.findByRole("textbox", { name: de["writing.workspace.editor.proseLabel"] });
    expect(screen.queryByText(/27\. Oktober/)).toBeNull();
  });

  it("NO sepia control ships — D18's cut", async () => {
    renderZen();
    await screen.findByRole("textbox", { name: de["writing.workspace.editor.proseLabel"] });
    expect(screen.queryByText(/sepia/i)).toBeNull();
    expect(screen.queryByRole("button", { name: /sepia/i })).toBeNull();
  });

  it("the exit chip hands the leave to the page (the flush-first rule lives there)", async () => {
    const { onExit } = renderZen();
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.zen.exit"] }));
    expect(onExit).toHaveBeenCalledTimes(1);
  });

  it("a busy exit holds the chip and locks the prose — the swap window's face", async () => {
    const { onExit } = renderZen({ zenBusy: true });
    // The chip wears the family's busy face: the busy label, disabled.
    const chip = screen.getByRole("button", { name: de["writing.workspace.zen.exitBusy"] });
    expect(chip.hasAttribute("disabled")).toBe(true);
    fireEvent.click(chip);
    expect(onExit).not.toHaveBeenCalled();
    // The room's prose is locked — keystrokes in the window would die with
    // the unmount (the refetched body predates them).
    const box = await screen.findByRole("textbox", { name: de["writing.workspace.editor.proseLabel"] });
    await waitFor(() => expect(box.getAttribute("contenteditable")).toBe("false"));
  });
});

describe("the counters — today real, session real", () => {
  it("today reads the aggregate's net, the session starts at zero", async () => {
    renderZen({ todayWords: 412 });
    expect(await screen.findByText(/Heute: \+412 W · Sitzung: 0 W/)).toBeTruthy();
  });

  it("a removed day keeps its sign — honest, never hidden", async () => {
    renderZen({ todayWords: -120 });
    expect(await screen.findByText(/Heute: -120 W/)).toBeTruthy();
  });

  it("an unavailable aggregate keeps the neutral — never an invented number", async () => {
    renderZen({ todayWords: null });
    expect(await screen.findByText(/Heute: — · Sitzung: 0 W/)).toBeTruthy();
  });

  it("the session counts the live delta since entry — typing moves it", async () => {
    const { onBodyChange } = renderZen();
    const box = await screen.findByRole("textbox", { name: de["writing.workspace.editor.proseLabel"] });
    await waitFor(() => expect(box.textContent).toContain("Dritter Absatz"));
    // Keyboard-only typing (the page test's own discipline): jsdom lays out
    // nothing, ProseMirror's pointer path reads geometry that is not there.
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    box.focus();
    await user.keyboard(" Zwei mehr.");
    expect(await screen.findByText(/Sitzung: 2 W/)).toBeTruthy();
    // The edit rides the page's one write path.
    expect(onBodyChange).toHaveBeenCalled();
    expect(vi.mocked(onBodyChange).mock.calls.at(-1)?.[0]).toContain("Zwei mehr.");
  });
});

describe("the pomodoro — session-only, frontend-real", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("starts at 25:00 running, counts down, pause holds, reset restores", async () => {
    renderZen();
    const room = screen.getByRole("dialog");
    expect(within(room).getByText("25:00")).toBeTruthy();
    act(() => vi.advanceTimersByTime(61_000));
    expect(within(room).getByText("23:59")).toBeTruthy();
    fireEvent.click(within(room).getByRole("button", { name: de["writing.workspace.zen.timer.pause"] }));
    act(() => vi.advanceTimersByTime(30_000));
    expect(within(room).getByText("23:59")).toBeTruthy();
    fireEvent.click(within(room).getByRole("button", { name: de["writing.workspace.zen.timer.resume"] }));
    act(() => vi.advanceTimersByTime(5_000));
    expect(within(room).getByText("23:54")).toBeTruthy();
    fireEvent.click(within(room).getByRole("button", { name: de["writing.workspace.zen.timer.reset"] }));
    expect(within(room).getByText("25:00")).toBeTruthy();
  });

  it("writes nothing to storage — the session is the whole lifetime", async () => {
    const local = vi.spyOn(Storage.prototype, "setItem");
    renderZen();
    act(() => vi.advanceTimersByTime(120_000));
    expect(local).not.toHaveBeenCalled();
  });
});

describe("the focus presets — dim honestly, cycle honestly", () => {
  it("Absatz-Fokus is the entry mode: the caret's paragraph stands, the rest dim", async () => {
    renderZen();
    const box = await screen.findByRole("textbox", { name: de["writing.workspace.editor.proseLabel"] });
    // The entry focuses the prose tail — the caret sits in the last paragraph.
    await waitFor(() => {
      const paragraphs = box.querySelectorAll("p");
      expect(paragraphs).toHaveLength(3);
      expect(paragraphs[2].className).toContain("zen-active-block");
    });
    const paragraphs = box.querySelectorAll("p");
    expect(paragraphs[0].className).toContain("zen-dim-block");
    expect(paragraphs[1].className).toContain("zen-dim-block");
    expect(paragraphs[2].className).not.toContain("zen-dim-block");
    expect(
      screen.getByRole("button", { name: de["writing.workspace.zen.focus.paragraph"] }).getAttribute("aria-pressed"),
    ).toBe("true");
  });

  it("Satz-Fokus dims the text outside the caret's sentence — inline, not by paragraph", async () => {
    const body = "Eins zwei.\n\nDrei vier. Fünf sechs. Sieben acht.";
    renderZen({ entry: { scene: { ...SCENE, body }, chapter: CHAPTER } });
    const box = await screen.findByRole("textbox", { name: de["writing.workspace.editor.proseLabel"] });
    await waitFor(() => expect(box.textContent).toContain("Sieben acht."));
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.zen.focus.sentence"] }));
    await waitFor(() => {
      const paragraphs = box.querySelectorAll("p");
      // The caret rests at the tail: the last sentence stands, the earlier
      // ones in the same paragraph dim inline, the first paragraph wholly.
      expect(paragraphs[0].querySelectorAll(".zen-dim-inline").length).toBeGreaterThan(0);
      expect(paragraphs[1].querySelectorAll(".zen-dim-inline").length).toBeGreaterThan(0);
      expect(paragraphs[1].textContent).toContain("Sieben acht.");
    });
    const paragraphs = box.querySelectorAll("p");
    expect(paragraphs[1].querySelector(".zen-dim-inline")?.textContent).toContain("Drei vier.");
    expect(paragraphs[1].querySelector(".zen-dim-inline")?.textContent).not.toContain("Sieben acht.");
    expect(box.querySelector(".zen-active-block")).toBeNull();
    expect(
      screen.getByRole("button", { name: de["writing.workspace.zen.focus.sentence"] }).getAttribute("aria-pressed"),
    ).toBe("true");
  });

  it("Normal dims nothing — the whole prose at full strength", async () => {
    renderZen();
    const box = await screen.findByRole("textbox", { name: de["writing.workspace.editor.proseLabel"] });
    await waitFor(() => expect(box.querySelectorAll("p")).toHaveLength(3));
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.zen.focus.normal"] }));
    await waitFor(() => expect(box.querySelector(".zen-active-block")).toBeNull());
    expect(box.querySelector(".zen-dim-block")).toBeNull();
    expect(box.querySelector(".zen-dim-inline")).toBeNull();
    expect(
      screen.getByRole("button", { name: de["writing.workspace.zen.focus.normal"] }).getAttribute("aria-pressed"),
    ).toBe("true");
  });
});

describe("the soundscape — disabled with the gap note (row 12, INTERIM #877)", () => {
  it("the control ships disabled, locked, with the drafted note", async () => {
    renderZen();
    const button = screen.getByRole("button", { name: de["writing.workspace.zen.soundscape"] });
    expect(button.hasAttribute("disabled")).toBe(true);
    expect(button.getAttribute("title")).toBe(de["writing.workspace.zen.soundscapeNote"]);
    expect(button.getAttribute("title")).toBe("Klanglandschaften kommen in einer späteren Welle");
  });
});

describe("the ghost inside zen — PR 4's seam stays reachable", () => {
  it("the prompt bar asks from inside the room", async () => {
    const { continuation } = renderZen();
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.promptBar.continue"] }));
    expect(continuation.start).toHaveBeenCalledWith(undefined);
  });

  it("a pending proposal stands at the tail; Tab accepts into the one write path", async () => {
    const dismiss = vi.fn();
    const { onBodyChange } = renderZen({
      continuation: continuationOf({ phase: "pending", text: "Der Vorschlag steht.", dismiss }),
    });
    const box = await screen.findByRole("textbox", { name: de["writing.workspace.editor.proseLabel"] });
    await waitFor(() => expect(box.textContent).toContain("Dritter Absatz"));
    expect(screen.getByTestId("ghost-preview").textContent).toContain("Der Vorschlag steht.");
    fireEvent.keyDown(box, { key: "Tab" });
    await waitFor(() => expect(onBodyChange).toHaveBeenCalled());
    expect(vi.mocked(onBodyChange).mock.calls.at(-1)?.[0]).toBe(`${BODY}\n\nDer Vorschlag steht.`);
    expect(dismiss).toHaveBeenCalled();
  });

  it("the error face stands in zen too — retry and discard reachable", async () => {
    const retry = vi.fn();
    const dismiss = vi.fn();
    renderZen({ continuation: continuationOf({ phase: "error", errorCode: "network", retry, dismiss }) });
    const face = await screen.findByTestId("ghost-error");
    fireEvent.click(within(face).getByRole("button", { name: de["writing.workspace.ghost.retry"] }));
    expect(retry).toHaveBeenCalled();
    fireEvent.click(within(face).getByRole("button", { name: de["writing.workspace.ghost.discard"] }));
    expect(dismiss).toHaveBeenCalled();
  });
});

describe("the room's keyboard discipline", () => {
  it("Tab wraps inside the zen surface — the covered chrome keeps no focus", async () => {
    renderZen();
    const room = screen.getByRole("dialog");
    await screen.findByRole("textbox", { name: de["writing.workspace.editor.proseLabel"] });
    const focusable = room.querySelectorAll<HTMLElement>(
      'button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"]), [contenteditable="true"]',
    );
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    last.focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(first);
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(last);
  });

  it("the fullscreen toggle asks the browser — the draft's own control", async () => {
    const request = vi.fn().mockResolvedValue(undefined);
    document.documentElement.requestFullscreen = request;
    renderZen();
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.zen.fullscreen"] }));
    expect(request).toHaveBeenCalledTimes(1);
  });
});
