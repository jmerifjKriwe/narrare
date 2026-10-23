// @vitest-environment jsdom
/**
 * The ghost-text contract at the caret, driven through the real TipTap: the
 * proposal renders as a decoration (in the DOM, never in the document), Tab
 * commits it, Esc drops it without reaching the window, and an accept while
 * an autosave PUT is in flight loses no text.
 *
 * The first import re-bases fetch onto a real local HTTP server (see
 * editorApiServer) — no module is mocked and no editor is faked; holding the
 * server's first response is what makes a save "in flight".
 */
import "./editorApiServer";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, beforeAll, afterEach, describe, expect, it } from "vitest";

import { editorServer, startEditorServer, stopEditorServer } from "./editorApiServer";
import { t } from "@shell/lib/i18n";

import { ChapterEditor } from "./ChapterEditor";

const CHAPTER = "2f0b8a52-9d3e-4f6e-8df5-7db9df0f4a51";

// jsdom lays out nothing: Element geometry reports zeros, but Range geometry
// is simply missing — and ProseMirror reads Range rects whenever it scrolls
// a selection into view (after typing, after focus). Hand it the same zeros
// the elements already claim, so "nothing to scroll" is the only answer.
const zeroRect = { top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0, x: 0, y: 0 } as DOMRect;
Range.prototype.getClientRects = function (): DOMRectList {
  return [zeroRect] as unknown as DOMRectList;
};
Range.prototype.getBoundingClientRect = () => zeroRect;

beforeAll(startEditorServer);
afterAll(stopEditorServer);

afterEach(() => {
  cleanup();
  for (const request of editorServer.requests) request.respond();
  editorServer.requests.length = 0;
  editorServer.holdNext = 0;
});

/** What the live region says across both of its logs. Announcements linger
 *  for seconds by design, so every test asserts a message only it can have
 *  caused — that is the bleed-proof form of the check. */
function announced(): string {
  return document.querySelector("[data-live-announcer]")?.textContent ?? "";
}

/** The document's own text: the editor DOM as ProseMirror renders it, with
 *  every ghost widget removed — the ghost never shows up here until Tab. */
function documentText(): string {
  const editable = document.querySelector(".ProseMirror");
  if (!editable) return "";
  const documentClone = editable.cloneNode(true) as HTMLElement;
  documentClone.querySelectorAll(".ghost").forEach((node) => node.remove());
  return documentClone.textContent ?? "";
}

/** The editor element, once TipTap has mounted it. */
async function editorElement(): Promise<HTMLElement> {
  return waitFor(() => {
    const editable = document.querySelector<HTMLElement>(".ProseMirror");
    expect(editable).not.toBeNull();
    return editable as HTMLElement;
  });
}

async function focusEditor(): Promise<ReturnType<typeof userEvent.setup>> {
  const user = userEvent.setup({ pointerEventsCheck: 0 });
  (await editorElement()).focus();
  return user;
}

describe("ChapterEditor's ghost text", () => {
  it("renders the proposal as decoration, not document", async () => {
    const resolved: boolean[] = [];
    render(
      <ChapterEditor
        chapterId={CHAPTER}
        body="Anfang."
        proposal="Der Vorschlag des Geistes."
        onProposalResolve={(accepted) => resolved.push(accepted)}
      />,
    );

    const ghost = await screen.findByText("Der Vorschlag des Geistes.");
    expect(ghost.closest(".ghost")).not.toBeNull();
    // The proof of "decoration, not document": strip the widget from a copy
    // of the editor DOM and not one letter of the proposal remains.
    expect(documentText()).not.toContain("Vorschlag");
    await waitFor(() => expect(announced()).toContain(t("editor.ghostArrived")));
    expect(resolved).toEqual([]);
  });

  it("commits the ghost into document and autosave on Tab", { timeout: 10_000 }, async () => {
    const resolved: boolean[] = [];
    render(
      <ChapterEditor
        chapterId={CHAPTER}
        body=""
        proposal="Nimm mich auf."
        onProposalResolve={(accepted) => resolved.push(accepted)}
      />,
    );
    const user = await focusEditor();
    await screen.findByText("Nimm mich auf.");

    await user.keyboard("{Tab}");

    // The widget is spent; its text belongs to the document now — the same
    // words exist, but as document content, not as a ghost.
    expect(document.querySelector(".ghost")).toBeNull();
    expect(documentText()).toContain("Nimm mich auf.");
    await waitFor(() => expect(announced()).toContain(t("editor.ghostAccepted")));
    expect(resolved).toEqual([true]);
    // The debounced autosave (800 ms) persists exactly what was accepted.
    await waitFor(() => expect(editorServer.requests.length).toBe(1), { timeout: 4_000 });
    expect(editorServer.requests[0].url).toContain(`/api/writing/chapters/${CHAPTER}`);
    expect(editorServer.requests[0].body).toContain("Nimm mich auf.");
  });

  it("drops the ghost on Escape without document, save or window", { timeout: 10_000 }, async () => {
    const resolved: boolean[] = [];
    render(
      <ChapterEditor
        chapterId={CHAPTER}
        body=""
        proposal="Weg damit."
        onProposalResolve={(accepted) => resolved.push(accepted)}
      />,
    );
    const user = await focusEditor();
    await screen.findByText("Weg damit.");

    // The seam in the other direction: a window keydown listener standing
    // in for NovelPage's focus stepper must never see the handled Esc.
    const seenAtWindow: KeyboardEvent[] = [];
    const witness = (event: KeyboardEvent) => seenAtWindow.push(event);
    window.addEventListener("keydown", witness);

    await user.keyboard("{Escape}");

    window.removeEventListener("keydown", witness);
    expect(document.querySelector(".ghost")).toBeNull();
    expect(screen.queryByText("Weg damit.")).toBeNull();
    expect(documentText()).not.toContain("Weg damit.");
    await waitFor(() => expect(announced()).toContain(t("editor.ghostDiscarded")));
    expect(resolved).toEqual([false]);
    expect(seenAtWindow).toEqual([]);
    // A discarded proposal schedules nothing: no PUT ever left the page.
    expect(editorServer.requests).toEqual([]);

    // The seam in the editor's own direction: a ghost-free Esc is not the
    // editor's key — even though ProseMirror's core marks it handled, the
    // window must receive a clean copy or the focus stepper stands down
    // forever after the first ghost.
    const forwarded: KeyboardEvent[] = [];
    const catcher = (event: KeyboardEvent) => forwarded.push(event);
    window.addEventListener("keydown", catcher);
    await user.keyboard("{Escape}");
    window.removeEventListener("keydown", catcher);
    expect(forwarded.some((event) => event.key === "Escape" && !event.defaultPrevented)).toBe(
      true,
    );
  });

  it("loses no text when the ghost is accepted while a save is in flight", { timeout: 20_000 }, async () => {
    editorServer.holdNext = 1; // the typing's save stays unanswered — that is "in flight"
    const view = render(<ChapterEditor chapterId={CHAPTER} body="" proposal={null} />);
    const user = await focusEditor();
    // keyboard, not type: type() clicks first, and ProseMirror's mousedown
    // path needs the layout jsdom does not have. The editor already holds
    // the caret; the keys are the user's part.
    await user.keyboard("Handgeschrieben.");

    // Save one is away and holding; it knows nothing of the ghost yet.
    await waitFor(() => expect(editorServer.requests.length).toBe(1), { timeout: 4_000 });
    expect(editorServer.requests[0].body).toContain("Handgeschrieben.");
    expect(editorServer.requests[0].body).not.toContain("Geisterzählung");

    await view.rerender(
      <ChapterEditor chapterId={CHAPTER} body="" proposal="Und die Geisterzählung." />,
    );
    await screen.findByText("Und die Geisterzählung.");
    await user.keyboard("{Tab}");

    // The document holds everything at once — the typed text was not
    // displaced by the accept.
    expect(documentText()).toContain("Handgeschrieben.");
    expect(documentText()).toContain("Geisterzählung");
    // The accept's own save carries the whole document: the in-flight first
    // save having the older body costs nothing.
    await waitFor(() => expect(editorServer.requests.length).toBe(2), { timeout: 4_000 });
    expect(editorServer.requests[1].body).toContain("Handgeschrieben.");
    expect(editorServer.requests[1].body).toContain("Geisterzählung");
    editorServer.requests[0].respond();
  });
});
