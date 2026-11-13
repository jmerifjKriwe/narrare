// @vitest-environment jsdom
/**
 * The floating prompt bar's contract, at both of its levels.
 *
 * The bar itself (the draft's launcher): the composition is the draft's —
 * the style chip, the inline field and the Weiterschreiben trigger in one
 * pill, the three quick prompts beneath — and it is honest about what it
 * can send (D-4): the field and the pills stand `aria-disabled` with the
 * reason on their titles, the trigger names no style yet, and the one
 * control that does what it says is the Weiterschreiben trigger, which
 * freezes while the stream runs. The bar never steals focus on mount and
 * keeps the draft's keyboard order.
 *
 * The bar in the editor: the column mounts it below the card through the
 * editor's slot, it yields with the frame at focus depth 2, and its
 * trigger is the same continuation the runhead's button above the card
 * starts — which stays (the bar augments, never replaces).
 *
 * The first import re-bases fetch onto a real local HTTP server (see
 * editorApiServer); its scripted event-stream is what makes the wiring
 * test a real continuation, not a mock.
 */
import "../editorApiServer";

import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { editorServer, startEditorServer, stopEditorServer } from "../editorApiServer";
import { clearAnnouncements } from "@shell/lib/announce";
import { t } from "@shell/lib/i18n";
import type { Chapter } from "@shell/lib/api/client";

import { ChapterEditor } from "../ChapterEditor";
import { EditorColumn } from "./EditorColumn";
import { PromptBar } from "./PromptBar";

const CHAPTER = "2f0b8a52-9d3e-4f6e-8df5-7db9df0f4a51";
const NOVEL = "aa9ef131-0000-4000-8000-000000000001";

/** The SSE body a continuation is answered with: one `data:` frame per fact. */
function streamOf(...frames: object[]): string {
  return frames.map((frame) => `data: ${JSON.stringify(frame)}\n\n`).join("");
}

// jsdom lays out nothing: ProseMirror reads Range rects when it scrolls a
// selection into view. Hand it zeros, so "nothing to scroll" is the only
// answer (the editor test file's own patch).
const zeroRect = { top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0, x: 0, y: 0 } as DOMRect;
Range.prototype.getClientRects = function (): DOMRectList {
  return [zeroRect] as unknown as DOMRectList;
};
Range.prototype.getBoundingClientRect = () => zeroRect;

beforeAll(startEditorServer);
afterAll(stopEditorServer);

afterEach(() => {
  cleanup();
  editorServer.continuation?.finish();
  editorServer.continueWith = null;
  editorServer.refuseContinue = false;
  clearAnnouncements();
});

/** The bar as the column mounts it, through the editor's slot. */
function BarHarness(props: { disabled?: boolean; onContinue?: () => void }) {
  return <PromptBar onContinue={props.onContinue ?? (() => {})} disabled={props.disabled ?? false} />;
}

/** The editor as the editor-level cases mount it: the slot carrying the
 *  bar, the frame around it. `schedule` is a no-op — these cases stream,
 *  they never save. */
function EditorHarness(props: { focusDepth?: 0 | 1 | 2 }) {
  return (
    <ChapterEditor
      chapterId={CHAPTER}
      body="Anfang."
      title=""
      onTitleChange={() => {}}
      status="idle"
      schedule={() => {}}
      chapterNumber={1}
      focusDepth={props.focusDepth}
      promptBar={(controls) => <PromptBar {...controls} />}
    />
  );
}

/** The rail-less column around one open chapter — the least the mount
 *  case needs to see the card and the bar the column threads. */
function ColumnHarness() {
  const chapter: Chapter = {
    id: CHAPTER,
    novel_id: NOVEL,
    body: "Anfang.",
    title: "",
    position: 0,
    created_at: "2026-11-13T00:00:00Z",
    updated_at: "2026-11-13T00:00:00Z",
  };
  return (
    <EditorColumn
      railOverlay={false}
      dockOverlay={false}
      pending={false}
      failed={false}
      refreshFailed={false}
      orderFailed={false}
      showRail={false}
      current={chapter}
      chapterTotal={1}
      currentIndex={0}
      draftTitle=""
      status="idle"
      offer={null}
      bookTitle="Dead Signal"
      bookAuthor={undefined}
      focus={0}
      railFilter={null}
      retry={() => {}}
      onTitleChange={() => {}}
      schedule={() => {}}
      onProposalResolve={() => {}}
      onRenameOpen={() => {}}
      onDeleteOpen={() => {}}
      onMove={async () => {}}
    />
  );
}

describe("the prompt bar", () => {
  it("draws the drafted launcher — chip, field, trigger in one pill, the pills beneath", () => {
    render(<BarHarness />);

    const root = document.querySelector("[data-prompt-bar]")!;
    expect(root).not.toBeNull();
    // A named group: the bar speaks for itself before its controls speak.
    expect(root.getAttribute("role")).toBe("group");
    expect(root.getAttribute("aria-label")).toBe(t("chapters.promptBarLabel"));
    // The drafted pin: bottom of the scroll container on the desktop, in
    // flow under the card below it.
    expect(root.className).toContain("lg:sticky");
    expect(root.className).toContain("lg:bottom-6");

    // The draft's order: context trigger, inline field, Weiterschreiben —
    // then the quick prompts under the launcher.
    const chip = root.querySelector("[data-prompt-style]")!;
    const field = root.querySelector("[data-prompt-input]")!;
    const trigger = root.querySelector("[data-prompt-continue]")!;
    const pills = root.querySelector("[data-prompt-quicks]")!;
    expect(chip).not.toBeNull();
    expect(field).not.toBeNull();
    expect(trigger).not.toBeNull();
    expect(pills).not.toBeNull();
    expect(chip.compareDocumentPosition(field) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(field.compareDocumentPosition(trigger) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(trigger.compareDocumentPosition(pills) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("names no style yet — the trigger chip is the neutral placeholder, not a control", () => {
    render(<BarHarness />);

    // interim: no style presets — #821
    const chip = document.querySelector("[data-prompt-style]")!;
    expect(chip.tagName).toBe("SPAN");
    expect(chip.textContent).toBe(t("chapters.promptStyle"));
    expect(chip.querySelector("button")).toBeNull();
  });

  it("is honest about what it can send: the field and the pills stand aria-disabled with the reason", () => {
    render(<BarHarness />);

    // The field: dressed, but unable to take a prompt — readonly so the
    // reason on its title stays reachable by keyboard and reader alike.
    const field = document.querySelector("[data-prompt-input]") as HTMLInputElement;
    expect(field.getAttribute("aria-disabled")).toBe("true");
    expect(field.readOnly).toBe(true);
    expect(field.getAttribute("title")).toBe(t("chapters.promptDisabled"));
    expect(field.getAttribute("aria-label")).toBe(t("chapters.promptLabel"));
    expect(field.getAttribute("placeholder")).toBe(t("chapters.promptPlaceholder"));

    // interim: no prompt parameter on the continuation endpoint — #822
    const pills = within(document.querySelector("[data-prompt-quicks]") as HTMLElement).getAllByRole(
      "button",
    );
    expect(pills.map((pill) => pill.textContent)).toEqual([
      t("chapters.promptQuickTension"),
      t("chapters.promptQuickDialogue"),
      t("chapters.promptQuickDetail"),
    ]);
    for (const pill of pills) {
      expect(pill.getAttribute("aria-disabled")).toBe("true");
      expect(pill.getAttribute("title")).toBe(t("chapters.promptDisabled"));
    }
  });

  it("wears the drafted trigger: the Weiterschreiben pill in the terracotta cover ground", () => {
    render(<BarHarness />);

    const trigger = document.querySelector("[data-prompt-continue]") as HTMLButtonElement;
    expect(trigger.textContent).toContain(t("chapters.continue"));
    expect(trigger.className).toContain("rounded-full");
    expect(trigger.className).toContain("bg-cover-sepia");
    // The spark rides the trigger, hidden — the words name the button.
    expect(trigger.querySelector("svg")).not.toBeNull();
    expect(trigger.disabled).toBe(false);
  });

  it("fires the continuation from the trigger — and freezes the trigger while the stream runs", async () => {
    const calls: number[] = [];
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    const view = render(<BarHarness onContinue={() => calls.push(1)} />);

    await user.click(screen.getByRole("button", { name: t("chapters.continue") }));
    expect(calls).toEqual([1]);

    // Streaming: the editor holds `disabled` true until its stream settles.
    view.rerender(<BarHarness onContinue={() => calls.push(1)} disabled />);
    const trigger = document.querySelector("[data-prompt-continue]") as HTMLButtonElement;
    expect(trigger.disabled).toBe(true);
    await user.click(trigger);
    expect(calls).toEqual([1]);

    // The honest controls stay honest while the stream runs.
    expect(document.querySelector("[data-prompt-input]")!.getAttribute("aria-disabled")).toBe("true");
    view.rerender(<BarHarness onContinue={() => calls.push(1)} />);
    expect((document.querySelector("[data-prompt-continue]") as HTMLButtonElement).disabled).toBe(false);
  });

  it("mounts without stealing focus", () => {
    render(<BarHarness />);
    expect(document.activeElement).toBe(document.body);
  });

  it("keeps the draft's keyboard order: field, trigger, pills", () => {
    render(<BarHarness />);

    const root = document.querySelector("[data-prompt-bar]")!;
    const focusables = [...root.querySelectorAll("input, button")];
    expect(
      focusables.map((el) =>
        el.matches("[data-prompt-input]")
          ? "field"
          : el.matches("[data-prompt-continue]")
            ? "trigger"
            : "pill",
      ),
    ).toEqual(["field", "trigger", "pill", "pill", "pill"]);
  });
});

describe("the bar in the editor", () => {
  it("is mounted by the column below the card, and steals no focus on arrival", () => {
    render(<ColumnHarness />);

    const card = document.querySelector("[data-editor-card]")!;
    const bar = document.querySelector("[data-prompt-bar]")!;
    expect(card).not.toBeNull();
    expect(bar).not.toBeNull();
    expect(card.compareDocumentPosition(bar) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(bar.contains(document.activeElement)).toBe(false);
  });

  it("yields with the frame at focus depth 2", () => {
    const view = render(<EditorHarness focusDepth={0} />);
    expect(document.querySelector("[data-prompt-bar]")).not.toBeNull();

    view.rerender(<EditorHarness focusDepth={2} />);
    expect(document.querySelector("[data-prompt-bar]")).toBeNull();
  });

  it("augments, never replaces: the runhead's trigger stays and the bar runs the same continuation", async () => {
    // Both triggers carry the draft's words; the runhead's stands first,
    // above the card, where it always stood.
    editorServer.continueWith = streamOf({ delta: "Der Nebel " }, { delta: "hob sich vom See." });
    render(<EditorHarness />);
    const triggers = await waitFor(() => {
      const found = screen.getAllByRole("button", { name: t("chapters.continue") });
      expect(found.length).toBe(2);
      return found;
    });
    expect(triggers[0]!.closest("[data-prompt-bar]")).toBeNull();

    // The bar's trigger streams into the ghost — the editor's own
    // continuation, not a second one.
    const bar = document.querySelector("[data-prompt-bar]") as HTMLElement;
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    await user.click(within(bar).getByRole("button", { name: t("chapters.continue") }));
    await waitFor(() =>
      expect(document.querySelector(".ghost")?.textContent).toBe("Der Nebel hob sich vom See."),
    );
  });
});
