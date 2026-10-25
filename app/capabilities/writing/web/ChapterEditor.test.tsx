// @vitest-environment jsdom
/**
 * The ghost-text contract at the caret, driven through the real TipTap: the
 * proposal renders as a decoration (in the DOM, never in the document), Tab
 * commits it, Esc drops it without reaching the window, a ghost-free Esc
 * reaches the window exactly once — as a clean copy carrying the physical
 * key's code — a superseding offer announces its replacement once, a
 * growing stream announces nothing per delta, a failed stream names its
 * failure rather than a discard — but stays silent while an offer owns
 * the screen — a refused continuation announces the failure instead of
 * nothing, and an accept while an autosave PUT is in flight loses no
 * text.
 *
 * The first import re-bases fetch onto a real local HTTP server (see
 * editorApiServer) — no module is mocked and no editor is faked; holding the
 * server's first response is what makes a save "in flight", and its scripted
 * event-stream is what makes a continuation succeed, grow or die.
 */
import "./editorApiServer";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, beforeAll, afterEach, describe, expect, it } from "vitest";

import { editorServer, startEditorServer, stopEditorServer } from "./editorApiServer";
import { clearAnnouncements } from "@shell/lib/announce";
import { t } from "@shell/lib/i18n";

import { ChapterEditor } from "./ChapterEditor";

const CHAPTER = "2f0b8a52-9d3e-4f6e-8df5-7db9df0f4a51";

/** The SSE body a continuation is answered with: one `data:` frame per
 * fact, or a raw frame where a test needs the router's own bytes. */
function streamOf(...frames: (object | string)[]): string {
  return frames
    .map((frame) => (typeof frame === "string" ? frame : `data: ${JSON.stringify(frame)}\n\n`))
    .join("");
}

/** How a dead provider ends the stream: the router's own error frame, byte
 * for byte (writing/router.py) — `event: error` with an empty payload, not
 * a `data:` shape no endpoint emits. */
const PROVIDER_DIED = "event: error\ndata: {}\n\n";

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
  // The live region is a body-level singleton that outlives every
  // component: its nodes linger for seven seconds by design. Clearing it
  // between cases keeps every baseline at zero — no earlier case's
  // announcement can bleed in, and none can expire mid-case on a slow
  // runner and take a count down with it.
  clearAnnouncements();
  for (const request of editorServer.requests) request.respond();
  editorServer.requests.length = 0;
  editorServer.holdNext = 0;
  editorServer.continueWith = null;
  editorServer.refuseContinue = false;
});

/** What the live region says across both of its logs. Announcements linger
 *  for seconds by design, so every test asserts a message only it can have
 *  caused — that is the bleed-proof form of the check. */
function announced(): string {
  return document.querySelector("[data-live-announcer]")?.textContent ?? "";
}

/** How often the live region holds one exact announcement. Every announce
 *  appends its own node to a log (the region accumulates for seven seconds),
 *  so counting the nodes counts the announcements — the witness for "once
 *  per supersede, never per delta". */
function announcementsOf(copy: string): number {
  return [...document.querySelectorAll('[data-live-announcer] [role="log"] > div')].filter(
    (node) => node.textContent === copy,
  ).length;
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
    // forever after the first ghost. The copy stands IN for the physical
    // key: the window sees exactly one Esc (no double-fire for a listener
    // that does not check defaultPrevented), and it carries the physical
    // key's code fields so future listeners can discriminate.
    const physical: KeyboardEvent[] = [];
    const atDocument = (event: KeyboardEvent) => physical.push(event);
    const atWindow: KeyboardEvent[] = [];
    const throughWindow = (event: KeyboardEvent) => atWindow.push(event);
    document.addEventListener("keydown", atDocument, true);
    window.addEventListener("keydown", throughWindow);
    // The physical key arrives the way a browser delivers it, not the way
    // userEvent's simulation does: real keydowns carry the legacy keyCode
    // (27 for Escape) while userEvent's omit it — an equality between the
    // two events' keyCode would read 0 on both sides and pass vacuously,
    // which is exactly what the literal below pins away.
    (await editorElement()).dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "Escape",
        code: "Escape",
        keyCode: 27,
        bubbles: true,
        cancelable: true,
      }),
    );
    document.removeEventListener("keydown", atDocument, true);
    window.removeEventListener("keydown", throughWindow);
    expect(physical).toHaveLength(1);
    expect(atWindow).toHaveLength(1);
    expect(atWindow[0]!.key).toBe("Escape");
    expect(atWindow[0]!.defaultPrevented).toBe(false);
    expect(atWindow[0]!.code).toBe(physical[0]!.code);
    expect(atWindow[0]!.keyCode).toBe(27);
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

  it("announces a superseding offer once per supersede", { timeout: 10_000 }, async () => {
    // Announcements linger in the region for seconds; every count below is
    // a delta against the moment the test starts, so what earlier tests
    // announced there cannot bleed into the verdict.
    const before = {
      arrived: announcementsOf(t("editor.ghostArrived")),
      replaced: announcementsOf(t("editor.ghostReplaced")),
    };
    const view = render(<ChapterEditor chapterId={CHAPTER} body="" proposal="Das erste Angebot." />);
    await screen.findByText("Das erste Angebot.");
    await waitFor(() =>
      expect(announcementsOf(t("editor.ghostArrived"))).toBe(before.arrived + 1),
    );

    // The bus is last-wins: a second offer replaces the pending ghost —
    // announced once, as a replacement, never as a second arrival.
    await view.rerender(
      <ChapterEditor chapterId={CHAPTER} body="" proposal="Das zweite Angebot." />,
    );
    await screen.findByText("Das zweite Angebot.");
    expect(announcementsOf(t("editor.ghostReplaced"))).toBe(before.replaced + 1);
    expect(announcementsOf(t("editor.ghostArrived"))).toBe(before.arrived + 1);

    // And a third: one announcement per supersede, not one per render.
    await view.rerender(
      <ChapterEditor chapterId={CHAPTER} body="" proposal="Das dritte Angebot." />,
    );
    await screen.findByText("Das dritte Angebot.");
    expect(announcementsOf(t("editor.ghostReplaced"))).toBe(before.replaced + 2);
    expect(announcementsOf(t("editor.ghostArrived"))).toBe(before.arrived + 1);
    expect(document.querySelector(".ghost")).not.toBeNull();
  });

  it("starts every case with a cleared live region", () => {
    // The witness for the between-cases clearAnnouncer: the cases before
    // this one announced arrivals, accepts, discards and replacements,
    // and none of it is measurable anymore — a baseline taken now counts
    // zero nodes, so it can neither bleed an earlier case's announcement
    // in nor lose one to the region's seven-second expiry on a slow
    // runner. Meaningful in a full run of the file (cases run in order);
    // vacuously green when this case runs alone.
    expect(announcementsOf(t("editor.ghostArrived"))).toBe(0);
    expect(announcementsOf(t("editor.ghostReplaced"))).toBe(0);
    expect(announcementsOf(t("editor.ghostAccepted"))).toBe(0);
    expect(announcementsOf(t("editor.ghostDiscarded"))).toBe(0);
  });

  it("announces a growing stream once, never per delta", { timeout: 10_000 }, async () => {
    const before = {
      arrived: announcementsOf(t("editor.ghostArrived")),
      replaced: announcementsOf(t("editor.ghostReplaced")),
    };
    editorServer.continueWith = streamOf(
      { delta: "Der Nebel " },
      { delta: "hob sich " },
      { delta: "vom See." },
    );
    // No proposal prop: the floor is the component's own stream (null would
    // be the explicit "no proposal" opinion, and the prop wins over the
    // stream — the ghost would never show).
    render(<ChapterEditor chapterId={CHAPTER} body="" />);
    const user = await focusEditor();
    await user.click(screen.getByRole("button", { name: t("chapters.continue") }));

    // The whole stream arrived: the ghost holds every delta.
    const ghost = await screen.findByText("Der Nebel hob sich vom See.");
    expect(ghost.closest(".ghost")).not.toBeNull();
    // One arrival announcement for the run — the deltas that grew it stayed
    // silent, and no replacement was announced (nothing superseded).
    await waitFor(() =>
      expect(announcementsOf(t("editor.ghostArrived"))).toBe(before.arrived + 1),
    );
    expect(announcementsOf(t("editor.ghostReplaced"))).toBe(before.replaced);
  });

  it("announces a failed stream as failed, not as discarded", { timeout: 10_000 }, async () => {
    const before = {
      failed: announcementsOf(t("editor.ghostFailed")),
      discarded: announcementsOf(t("editor.ghostDiscarded")),
    };
    editorServer.continueWith = streamOf({ delta: "Ein Anfang," }, PROVIDER_DIED);
    render(<ChapterEditor chapterId={CHAPTER} body="" />);
    const user = await focusEditor();
    await user.click(screen.getByRole("button", { name: t("chapters.continue") }));

    // The error frame replaces the done frame: nothing of the suggestion
    // remains, the failure is on screen — and the announcement names the
    // failure. It does not claim the user discarded anything: only the
    // user's own Esc may say that.
    await waitFor(() => expect(document.querySelector(".ghost")).toBeNull());
    expect(screen.getByRole("alert").textContent).toContain(t("chapters.continueError"));
    await waitFor(() => expect(announcementsOf(t("editor.ghostFailed"))).toBe(before.failed + 1));
    expect(announcementsOf(t("editor.ghostDiscarded"))).toBe(before.discarded);
  });

  it("announces a refused continuation as a failure", { timeout: 10_000 }, async () => {
    const before = { failed: announcementsOf(t("editor.ghostFailed")) };
    editorServer.refuseContinue = true; // the server refuses before a word
    render(<ChapterEditor chapterId={CHAPTER} body="" />);
    const user = await focusEditor();
    await user.click(screen.getByRole("button", { name: t("chapters.continue") }));

    // The request was refused outright: no ghost ever showed, but the
    // failure is the truth of the click the user just made — the alert
    // shows it, and the announcement says it instead of nothing.
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toContain(t("chapters.continueError")),
    );
    await waitFor(() => expect(announcementsOf(t("editor.ghostFailed"))).toBe(before.failed + 1));
  });

  it("stays silent about a stream's failure while an offer owns the screen", { timeout: 10_000 }, async () => {
    const before = {
      failed: announcementsOf(t("editor.ghostFailed")),
      discarded: announcementsOf(t("editor.ghostDiscarded")),
    };
    editorServer.continueWith = streamOf({ delta: "Ein Anfang," }, PROVIDER_DIED);
    // The prop has an opinion, so its offer owns the ghost on screen —
    // the stream's own text never becomes the visible one.
    render(<ChapterEditor chapterId={CHAPTER} body="" proposal="Das Angebot bleibt." />);
    const user = await focusEditor();
    await screen.findByText("Das Angebot bleibt.");
    await user.click(screen.getByRole("button", { name: t("chapters.continue") }));

    // The stream died mid-word, but the ghost the user is looking at is
    // the offer's, and the offer is fine: it must not hear a failure
    // about a ghost that is not on screen. The alert still names the
    // refused request — that one is the user's.
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toContain(t("chapters.continueError")),
    );
    expect(screen.getByText("Das Angebot bleibt.")).toBeTruthy();
    expect(announcementsOf(t("editor.ghostFailed"))).toBe(before.failed);
    expect(announcementsOf(t("editor.ghostDiscarded"))).toBe(before.discarded);
  });
});
