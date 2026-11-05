// @vitest-environment jsdom
/**
 * The autosave's draft contract: the pending slot holds the whole document
 * — title beside body — and remembers which fields are dirty. The wire
 * carries only the dirty fields (a body edit never rewrites the title, a
 * rename never re-sends the text), a flush that finds both dirty sends
 * them as one request, and a refused write keeps its draft for the retry.
 *
 * The client is mocked at its module boundary: what these cases pin is the
 * composition of each request — which keys the payload carries — and the
 * draft's survival, not the wire itself (the editor suite drives the real
 * serialization against a real socket).
 */
import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const wire = vi.hoisted(() => ({
  /** The PUT bodies, in order — the composition of each request. */
  calls: [] as Array<{ title?: string; body?: string }>,
  /** Answer the next PUT with a refusal, once. */
  refuse: false,
}));

vi.mock("./api/client", () => ({
  client: {
    PUT: async (_path: string, init: { body: { title?: string; body?: string } }) => {
      wire.calls.push(init.body);
      if (wire.refuse) {
        wire.refuse = false;
        return { error: { detail: "refused" }, response: { ok: false } };
      }
      return { error: undefined, response: { ok: true } };
    },
  },
}));

import { useAutosave, type DocumentDraft } from "./save";

const CHAPTER = "2f0b8a52-9d3e-4f6e-8df5-7db9df0f4a51";

/** The hook's api, captured at render: `schedule`, `flush` and `discard`
 *  are stable, so the test drives them directly and reads the status from
 *  the DOM — the one thing a render owns. */
type Autosave = ReturnType<typeof useAutosave>;
let autosave!: Autosave;

function Probe(props: { onSaved?: (chapterId: string, draft: DocumentDraft) => void }) {
  autosave = useAutosave(CHAPTER, props.onSaved);
  return <p>{autosave.status}</p>;
}

/** Schedule and flush as one settled step: the flush clears the debounce,
 *  so no timer leaks into the next case. */
async function save(next: DocumentDraft, changed: keyof DocumentDraft): Promise<void> {
  act(() => autosave.schedule(next, changed));
  await act(async () => {
    await autosave.flush();
  });
}

afterEach(async () => {
  cleanup();
  // The hook's unmount cleanup flushes one last time; let that settle
  // before the next case's ledger starts, then clear both.
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
  wire.calls.length = 0;
  wire.refuse = false;
});

describe("useAutosave's draft", () => {
  it("a_body_only_save_sends_no_title", async () => {
    const saved: [string, DocumentDraft][] = [];
    render(<Probe onSaved={(id, draft) => saved.push([id, draft])} />);

    await save({ title: "Wald", body: "Der Satz." }, "body");

    expect(wire.calls).toStrictEqual([{ body: "Der Satz." }]);
    // The success carries the whole document — the page patches its cache
    // from the draft, not from the fields that happened to fly.
    expect(saved).toEqual([[CHAPTER, { title: "Wald", body: "Der Satz." }]]);
    expect(screen.getByText("saved")).toBeTruthy();
  });

  it("a_title_only_save_sends_no_body", async () => {
    render(<Probe />);

    await save({ title: "Wald", body: "Der alte Satz." }, "title");

    expect(wire.calls).toStrictEqual([{ title: "Wald" }]);
  });

  it("a_flush_carries_every_dirty_field", async () => {
    render(<Probe />);
    act(() => autosave.schedule({ title: "", body: "Text." }, "title"));
    await act(async () => {
      // A body edit joins the still-pending rename: one debounce, one
      // request, both fields — the latest draft is the whole truth.
      autosave.schedule({ title: "Wald", body: "Text." }, "body");
      await autosave.flush();
    });

    expect(wire.calls).toStrictEqual([{ title: "Wald", body: "Text." }]);
  });

  it("a_refused_save_keeps_its_draft", async () => {
    render(<Probe />);
    wire.refuse = true;
    act(() => autosave.schedule({ title: "Wald", body: "" }, "title"));
    await act(async () => {
      await autosave.flush();
    });
    expect(screen.getByText("failed")).toBeTruthy();

    // The refused draft survived: the retry sends the same title, still
    // dirty, and nothing else.
    await act(async () => {
      await autosave.flush();
    });
    expect(wire.calls).toStrictEqual([{ title: "Wald" }, { title: "Wald" }]);
    expect(screen.getByText("saved")).toBeTruthy();
  });
});
