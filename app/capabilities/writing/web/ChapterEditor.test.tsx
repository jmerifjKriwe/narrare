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
 * nothing, an accept while an autosave PUT is in flight loses no text,
 * and the arriving ghost owns the caret without waiting for a frame.
 *
 * The first import re-bases fetch onto a real local HTTP server (see
 * editorApiServer) — no module is mocked and no editor is faked; holding the
 * server's first response is what makes a save "in flight", and its scripted
 * event-stream is what makes a continuation succeed, grow or die.
 */
import "./editorApiServer";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useEffect } from "react";
import { afterAll, beforeAll, afterEach, describe, expect, it } from "vitest";

import { editorServer, startEditorServer, stopEditorServer } from "./editorApiServer";
import { clearAnnouncements } from "@shell/lib/announce";
import { t } from "@shell/lib/i18n";
import { useAutosave, unsavedStatus, type FlushOutcome } from "@shell/lib/save";

import { ChapterEditor } from "./ChapterEditor";

const CHAPTER = "2f0b8a52-9d3e-4f6e-8df5-7db9df0f4a51";

/** The editor as the page mounts it: the autosave hook above, `status` and
 *  `schedule` handed down — saving is not the editor's. The flush button
 *  stands where the page's leave paths call `save.flush()`. */
function Harness(props: { chapterId?: string; body?: string; proposal?: string | null;
  onProposalResolve?: (accepted: boolean) => void;
  onSaved?: (id: string, body: string) => void;
  onFlushed?: (outcome: FlushOutcome) => void }) {
  const save = useAutosave(props.chapterId ?? CHAPTER, props.onSaved);
  // NovelPage hands this predicate to the router blocker; jsdom has no
  // router, so the same function answers a dispatched event here — the
  // predicate itself is shared, not copied, so it cannot drift.
  useEffect(() => {
    /** Apply the page's unsaved-text predicate to the browser unload event. */
    function guard(event: BeforeUnloadEvent) {
      if (!unsavedStatus(save.status)) return;
      event.preventDefault();
      event.returnValue = "";
    }
    window.addEventListener("beforeunload", guard);
    return () => window.removeEventListener("beforeunload", guard);
  }, [save.status]);
  return (
    <>
      <ChapterEditor
        chapterId={props.chapterId ?? CHAPTER}
        body={props.body ?? ""}
        status={save.status}
        schedule={save.schedule}
        proposal={props.proposal}
        onProposalResolve={props.onProposalResolve}
      />
      <button type="button" onClick={async () => {
        const outcome = await save.flush();
        props.onFlushed?.(outcome);
      }}>flush</button>
      <button type="button" onClick={save.discard}>discard</button>
    </>
  );
}

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

afterEach(async () => {
  cleanup();
  // The unmount flush a failed save leaves behind is a real PUT on a real
  // socket, and it can land after this hook — where a one-shot flag the
  // next case sets would answer it instead of that case's own save. Writes
  // are serialized, so a straggler can arrive after the request it queued
  // behind has been answered: respond everything, wait, and repeat until a
  // quiet beat passes with nothing new on the wire.
  for (let quiet = 0; quiet < 3; ) {
    const arrived = editorServer.requests.splice(0);
    if (arrived.length === 0) quiet += 1;
    else {
      quiet = 0;
      for (const request of arrived) request.respond();
    }
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  // The live region is a body-level singleton that outlives every
  // component: its nodes linger for seven seconds by design. Clearing it
  // between cases keeps every baseline at zero — no earlier case's
  // announcement can bleed in, and none can expire mid-case on a slow
  // runner and take a count down with it.
  clearAnnouncements();
  editorServer.holdNext = 0;
  editorServer.continueWith = null;
  editorServer.refuseContinue = false;
  editorServer.refuseSave = false;
  editorServer.refuseSaveEmpty = false;
  editorServer.holdContinue = false;
  editorServer.breakContinue = false;
  editorServer.continuation?.finish();
  editorServer.continuation = null;
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

/** Focus the mounted editor and return the keyboard driver used by its tests. */
async function focusEditor(): Promise<ReturnType<typeof userEvent.setup>> {
  const user = userEvent.setup({ pointerEventsCheck: 0 });
  (await editorElement()).focus();
  return user;
}

describe("ChapterEditor's ghost text", () => {
  it("renders the proposal as decoration, not document", async () => {
    const resolved: boolean[] = [];
    render(
      <Harness
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

  it("owns the caret when the ghost arrives, so Esc alone discards it", async () => {
    // The condition CI hits: the frame callback has not run yet. The focus
    // command defers to requestAnimationFrame, and the click that started the
    // stream dropped the caret to <body> (React disables the focused button),
    // so a ghost painted one frame early is a ghost no key can reach: Esc
    // lands on <body> and the workbench's own Esc handler sees nothing to
    // stop. With no frame at all the gap is permanent, which is what makes
    // this deterministic instead of a race.
    const frame = window.requestAnimationFrame;
    window.requestAnimationFrame = () => 0;
    try {
      const resolved: boolean[] = [];
      render(
        <Harness
          chapterId={CHAPTER}
          body=""
          proposal="Weg damit."
          onProposalResolve={(accepted) => resolved.push(accepted)}
        />,
      );
      const ghost = await screen.findByText("Weg damit.");
      expect(ghost.closest(".ghost")).not.toBeNull();
      // The arrival hands the caret over itself — no test-supplied focus.
      expect(document.activeElement).toBe(document.querySelector(".ProseMirror"));

      // Nobody focused the editor by hand, so this Esc is the writer's own:
      // it belongs to the ghost, not to the workbench.
      const user = userEvent.setup({ pointerEventsCheck: 0 });
      await user.keyboard("{Escape}");

      expect(document.querySelector(".ghost")).toBeNull();
      await waitFor(() => expect(announced()).toContain(t("editor.ghostDiscarded")));
      expect(resolved).toEqual([false]);
      // A discarded proposal schedules nothing: no PUT ever left the page.
      expect(editorServer.requests).toEqual([]);
    } finally {
      window.requestAnimationFrame = frame;
    }
  });

  it("commits the ghost into document and autosave on Tab", { timeout: 10_000 }, async () => {
    const resolved: boolean[] = [];
    render(
      <Harness
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
      <Harness
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
    const view = render(<Harness chapterId={CHAPTER} body="" proposal={null} />);
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
      <Harness chapterId={CHAPTER} body="" proposal="Und die Geisterzählung." />,
    );
    await screen.findByText("Und die Geisterzählung.");
    await user.keyboard("{Tab}");

    // The document holds everything at once — the typed text was not
    // displaced by the accept.
    expect(documentText()).toContain("Handgeschrieben.");
    expect(documentText()).toContain("Geisterzählung");
    // The accept's own save carries the whole document. Writes are
    // serialized now, so it waits behind the held one: answering that is
    // what lets the accepted sentence go out.
    editorServer.requests[0].respond();
    await waitFor(() => expect(editorServer.requests.length).toBe(2), { timeout: 4_000 });
    expect(editorServer.requests[1].body).toContain("Handgeschrieben.");
    expect(editorServer.requests[1].body).toContain("Geisterzählung");
  });

  it("names a refused save, drops nothing and reports no save", { timeout: 10_000 }, async () => {
    const saved: [string, string][] = [];
    editorServer.refuseSave = true;
    render(
      <Harness
        chapterId={CHAPTER}
        body="Anfang."
        onSaved={(id, body) => saved.push([id, body])}
      />,
    );
    const user = await focusEditor();
    await user.keyboard("Der Satz.");
    await waitFor(
      // The repo's tests assert with plain Chai (no jest-dom): the alert's
      // own text is the witness, the idiom the continuation tests use.
      () => expect(screen.getByRole("alert").textContent).toContain(t("save.failed")),
      { timeout: 5000 },
    );
    expect(screen.queryByText(t("save.saved"))).toBeNull();
    expect(saved).toEqual([]);
    expect(document.querySelector(".ProseMirror")?.textContent).toContain("Der Satz.");
  });

  it("retries a failed save on the next keystroke and clears the failure", { timeout: 10_000 }, async () => {
    editorServer.refuseSave = true;
    render(<Harness chapterId={CHAPTER} body="" />);
    const user = await focusEditor();
    await user.keyboard("A");
    await screen.findByRole("alert", {}, { timeout: 5000 });
    editorServer.refuseSave = false;
    await user.keyboard("B");
    await waitFor(() => expect(screen.getByText(t("save.saved"))).toBeTruthy(), {
      timeout: 5000,
    });
    expect(editorServer.requests.at(-1)?.body).toContain("AB");
  });

  it("names a refusal that arrives with no body at all", { timeout: 10_000 }, async () => {
    // A proxy's 502, a bare 413: openapi-fetch parses `error` from the body
    // and finds nothing, so only the status line can tell this from a save.
    const saved: [string, string][] = [];
    editorServer.refuseSaveEmpty = true;
    render(<Harness body="" onSaved={(id, body) => saved.push([id, body])} />);
    const user = await focusEditor();
    await user.keyboard("Niemand hat das gespeichert.");
    await waitFor(
      () => expect(screen.getByRole("alert").textContent).toContain(t("save.failed")),
      { timeout: 5000 },
    );
    expect(screen.queryByText(t("save.saved"))).toBeNull();
    expect(saved).toEqual([]);
  });

  it("queues the newer body behind the one on the wire and only then says saved", { timeout: 10_000 }, async () => {
    editorServer.holdNext = 2;
    render(<Harness body="" />);
    const user = await focusEditor();
    await user.keyboard("Eins.");
    await waitFor(() => expect(editorServer.requests).toHaveLength(1));

    // Typing again while the first write is unanswered queues a second one
    // with the full document; the older answer must not clear it.
    await user.keyboard(" Zwei.");
    editorServer.requests[0].respond();
    await waitFor(() => expect(editorServer.requests).toHaveLength(2), { timeout: 4000 });
    expect(editorServer.requests[1].body).toContain("Eins. Zwei.");
    // The first answer saved the shorter body — the newer sentence is not on
    // the server yet, so the indicator must not claim it is.
    expect(screen.queryByText(t("save.saved"))).toBeNull();

    editorServer.requests[1].respond();
    await waitFor(() => expect(screen.getByText(t("save.saved"))).toBeTruthy(), {
      timeout: 5000,
    });
  });

  it("keeps flush pending until text typed during its PUT is saved", { timeout: 10_000 }, async () => {
    const outcomes: FlushOutcome[] = [];
    editorServer.holdNext = 2;
    render(<Harness onFlushed={(outcome) => outcomes.push(outcome)} />);
    const user = await focusEditor();
    await user.keyboard("Eins.");
    await user.click(screen.getByRole("button", { name: "flush" }));
    await waitFor(() => expect(editorServer.requests).toHaveLength(1));

    (await editorElement()).focus();
    await user.keyboard(" Zwei.");
    editorServer.requests[0].respond();
    await waitFor(() => expect(editorServer.requests).toHaveLength(2), { timeout: 4000 });
    expect(editorServer.requests[1].body).toContain("Eins. Zwei.");
    expect(outcomes).toEqual([]);
    expect(screen.queryByText(t("save.saved"))).toBeNull();

    editorServer.requests[1].respond();
    await waitFor(() => expect(outcomes).toEqual(["saved"]));
    expect(screen.getByText(t("save.saved"))).toBeTruthy();
  });

  it("reports failure if the newer body drained by flush is refused", { timeout: 10_000 }, async () => {
    const outcomes: FlushOutcome[] = [];
    editorServer.holdNext = 1;
    render(<Harness onFlushed={(outcome) => outcomes.push(outcome)} />);
    const user = await focusEditor();
    await user.keyboard("Eins.");
    await user.click(screen.getByRole("button", { name: "flush" }));
    await waitFor(() => expect(editorServer.requests).toHaveLength(1));

    (await editorElement()).focus();
    await user.keyboard(" Zwei.");
    editorServer.refuseSave = true;
    editorServer.requests[0].respond();
    await waitFor(() => expect(outcomes).toEqual(["failed"]));
    expect(screen.getByRole("alert").textContent).toContain(t("save.failed"));
    expect(documentText()).toContain("Eins. Zwei.");

    await user.click(screen.getByRole("button", { name: "flush" }));
    await waitFor(() => expect(outcomes).toEqual(["failed", "saved"]));
    expect(editorServer.requests.at(-1)?.body).toContain("Eins. Zwei.");
  });

  it("does not report a save that answers after the body was discarded", { timeout: 10_000 }, async () => {
    const saved: [string, string][] = [];
    editorServer.holdNext = 1;
    render(<Harness body="" onSaved={(id, body) => saved.push([id, body])} />);
    const user = await focusEditor();
    await user.keyboard("Zu spät.");
    await waitFor(() => expect(editorServer.requests).toHaveLength(1));

    await user.click(screen.getByRole("button", { name: "discard" }));
    editorServer.requests[0].respond();
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(screen.queryByText(t("save.saved"))).toBeNull();
    expect(saved).toEqual([]);
  });

  it("prevents beforeunload while a save is pending, not once it landed", { timeout: 10_000 }, async () => {
    /** The guard's answer to a tab close, as one cancelable event. */
    function unloadPrevented(): boolean {
      const event = new Event("beforeunload", { cancelable: true });
      window.dispatchEvent(event);
      return event.defaultPrevented;
    }
    render(<Harness chapterId={CHAPTER} body="" />);
    const user = await focusEditor();
    await user.keyboard("Noch nicht weg.");
    // Inside the 800 ms debounce the body exists nowhere but memory.
    expect(unloadPrevented()).toBe(true);
    await waitFor(() => expect(screen.getByText(t("save.saved"))).toBeTruthy(), {
      timeout: 5000,
    });
    // The server holds the text now; a close has nothing to lose.
    expect(unloadPrevented()).toBe(false);
  });

  it("announces a superseding offer once per supersede", { timeout: 10_000 }, async () => {
    // Announcements linger in the region for seconds; every count below is
    // a delta against the moment the test starts, so what earlier tests
    // announced there cannot bleed into the verdict.
    const before = {
      arrived: announcementsOf(t("editor.ghostArrived")),
      replaced: announcementsOf(t("editor.ghostReplaced")),
    };
    const view = render(<Harness chapterId={CHAPTER} body="" proposal="Das erste Angebot." />);
    await screen.findByText("Das erste Angebot.");
    await waitFor(() =>
      expect(announcementsOf(t("editor.ghostArrived"))).toBe(before.arrived + 1),
    );

    // The bus is last-wins: a second offer replaces the pending ghost —
    // announced once, as a replacement, never as a second arrival.
    await view.rerender(
      <Harness chapterId={CHAPTER} body="" proposal="Das zweite Angebot." />,
    );
    await screen.findByText("Das zweite Angebot.");
    expect(announcementsOf(t("editor.ghostReplaced"))).toBe(before.replaced + 1);
    expect(announcementsOf(t("editor.ghostArrived"))).toBe(before.arrived + 1);

    // And a third: one announcement per supersede, not one per render.
    await view.rerender(
      <Harness chapterId={CHAPTER} body="" proposal="Das dritte Angebot." />,
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
    render(<Harness chapterId={CHAPTER} body="" />);
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
    render(<Harness chapterId={CHAPTER} body="" />);
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
    render(<Harness chapterId={CHAPTER} body="" />);
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
    render(<Harness chapterId={CHAPTER} body="" proposal="Das Angebot bleibt." />);
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

  it("stops the continuation stream when the editor unmounts", { timeout: 10_000 }, async () => {
    // The continuation has no page to write into once the editor is gone —
    // the dock closed, the chapter switched. The stream must stop at the
    // fetch, not keep running unread on a dead socket.
    editorServer.continueWith = streamOf({ delta: "Der Nebel " });
    editorServer.holdContinue = true;
    const view = render(<Harness chapterId={CHAPTER} body="" />);
    const user = await focusEditor();
    await user.click(screen.getByRole("button", { name: t("chapters.continue") }));

    // The ghost is on screen from the stream's first delta, and the stream
    // is held open mid-flight. (The .ghost query, not findByText: the
    // delta's trailing space is real text the byText matcher will not
    // normalize away.)
    await waitFor(() => expect(document.querySelector(".ghost")?.textContent).toBe("Der Nebel "));
    const continuation = editorServer.continuation;
    expect(continuation).not.toBeNull();

    // The editor goes away. The connection must follow it.
    view.unmount();
    await Promise.race([
      continuation!.closed,
      new Promise((_, reject) =>
        setTimeout(
          () => reject(new Error("the continuation kept streaming after the editor unmounted")),
          5_000,
        ),
      ),
    ]);
  });

  it("names a continuation whose request itself dies", { timeout: 10_000 }, async () => {
    // A rejected POST — the API down, the wire cut before a word — is a
    // failure like a refusal: the alert shows it and the announcement says
    // it, and no rejection escapes the handler unnamed.
    const before = { failed: announcementsOf(t("editor.ghostFailed")) };
    editorServer.breakContinue = true;
    render(<Harness chapterId={CHAPTER} body="" />);
    const user = await focusEditor();
    await user.click(screen.getByRole("button", { name: t("chapters.continue") }));

    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toContain(t("chapters.continueError")),
    );
    await waitFor(() => expect(announcementsOf(t("editor.ghostFailed"))).toBe(before.failed + 1));
    const button = screen.getByRole("button", { name: t("chapters.continue") }) as HTMLButtonElement;
    await waitFor(() => expect(button.disabled).toBe(false)); // the finally ran
  });
});
