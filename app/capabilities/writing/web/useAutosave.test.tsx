// @vitest-environment jsdom
/**
 * The scene autosave (W4 Task 12) — the WP0b semantics the backend contract
 * expects, re-owned for prose scenes: an 800 ms debounce, a flush that
 * settles the latest draft before a leave, serialized writes, a refused
 * body that stays in memory and retries, and a status that tells the truth
 * (only a landed write is „saved"). The four-state vocabulary feeds the one
 * shell store the chrome reads. Fake timers drive the debounce; the PUT is
 * scripted at the client boundary, never faked below it.
 */
import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import { client } from "@shell/lib/api/client";
import { queryClient } from "@shell/lib/query";
import { getSaveStatus, setSaveStatus } from "@shell/lib/saveStatus";

import { AUTOSAVE_DELAY_MS, useAutosave } from "./useAutosave";

const api = client as unknown as { PUT: ReturnType<typeof vi.fn> };
const SCENE = "s1";
const CHAPTER = "c1";
const NOVEL = "n1";

function ok() {
  return { error: undefined, response: new Response(null, { status: 200 }) };
}
function refused() {
  return { error: { detail: "no" }, response: new Response(null, { status: 500 }) };
}

/** A PUT whose answer the test holds — the in-flight window. */
function deferred() {
  let resolve!: (value: ReturnType<typeof ok>) => void;
  const promise = new Promise<ReturnType<typeof ok>>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}

function mount() {
  return renderHook(() => useAutosave(SCENE, CHAPTER, NOVEL));
}

/** Advance the fake clock inside act, so the debounce's async write and the
 *  status it sets are flushed into the render the assertions read. */
async function tick(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  setSaveStatus("idle");
  api.PUT.mockResolvedValue(ok());
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.clearAllMocks();
  queryClient.clear();
  setSaveStatus("idle");
});

describe("the debounce", () => {
  it("a keystroke engages saving at once, but the wire waits out the window", async () => {
    const { result } = mount();
    act(() => result.current.schedule("Ein neuer Satz."));
    expect(result.current.status).toBe("saving");
    expect(result.current.unsaved).toBe(true);
    expect(api.PUT).not.toHaveBeenCalled();
    await tick(AUTOSAVE_DELAY_MS - 1);
    expect(api.PUT).not.toHaveBeenCalled();
    await tick(1);
    expect(api.PUT).toHaveBeenCalledTimes(1);
    expect(api.PUT).toHaveBeenCalledWith("/api/writing/scenes/{scene_id}", {
      params: { path: { scene_id: SCENE } },
      body: { body: "Ein neuer Satz." },
    });
    expect(result.current.status).toBe("saved");
    expect(getSaveStatus()).toBe("saved");
  });

  it("a later keystroke restarts the window and the flush carries the latest body", async () => {
    const { result } = mount();
    act(() => result.current.schedule("alt"));
    await tick(400);
    act(() => result.current.schedule("neu"));
    await tick(400);
    expect(api.PUT).not.toHaveBeenCalled();
    await tick(400);
    expect(api.PUT).toHaveBeenCalledTimes(1);
    expect(api.PUT.mock.calls[0][1].body).toEqual({ body: "neu" });
    expect(result.current.status).toBe("saved");
  });
});

describe("the flush", () => {
  it("settles the pending body immediately, without waiting out the debounce", async () => {
    const { result } = mount();
    act(() => result.current.schedule("sofort"));
    let outcome!: string;
    await act(async () => {
      outcome = await result.current.flush();
    });
    expect(outcome).toBe("saved");
    expect(api.PUT).toHaveBeenCalledTimes(1);
    expect(result.current.status).toBe("saved");
  });

  it("a clean hook flushes nothing", async () => {
    const { result } = mount();
    let outcome!: string;
    await act(async () => {
      outcome = await result.current.flush();
    });
    expect(outcome).toBe("clean");
    expect(api.PUT).not.toHaveBeenCalled();
  });

  it("a newer draft arriving mid-flight is not discarded — the flush carries it too", async () => {
    const gate = deferred();
    api.PUT.mockReturnValueOnce(gate.promise);
    const { result } = mount();
    act(() => result.current.schedule("erster"));
    let flushing!: Promise<string>;
    act(() => {
      flushing = result.current.flush();
    });
    await tick(0);
    expect(api.PUT).toHaveBeenCalledTimes(1);
    // A keystroke lands while the first PUT is on the wire.
    act(() => result.current.schedule("zweiter"));
    gate.resolve(ok());
    let outcome!: string;
    await act(async () => {
      outcome = await flushing;
    });
    expect(outcome).toBe("saved");
    expect(api.PUT).toHaveBeenCalledTimes(2);
    expect(api.PUT.mock.calls[1][1].body).toEqual({ body: "zweiter" });
    expect(result.current.status).toBe("saved");
  });
});

describe("the refused write", () => {
  it("names the failure, keeps the body, and only a landed retry clears it", async () => {
    api.PUT.mockResolvedValueOnce(refused());
    const { result } = mount();
    act(() => result.current.schedule("verloren?"));
    await tick(AUTOSAVE_DELAY_MS);
    expect(result.current.status).toBe("failed");
    expect(getSaveStatus()).toBe("failed");
    // The body stays in memory: a retry carries it again.
    api.PUT.mockResolvedValueOnce(ok());
    let outcome!: string;
    await act(async () => {
      outcome = await result.current.flush();
    });
    expect(outcome).toBe("saved");
    expect(api.PUT).toHaveBeenCalledTimes(2);
    expect(api.PUT.mock.calls[1][1].body).toEqual({ body: "verloren?" });
    expect(result.current.status).toBe("saved");
  });

  it("a keystroke after a failure keeps the failure named — no flicker", async () => {
    api.PUT.mockResolvedValueOnce(refused());
    const { result } = mount();
    act(() => result.current.schedule("erst"));
    await tick(AUTOSAVE_DELAY_MS);
    expect(result.current.status).toBe("failed");
    act(() => result.current.schedule("zweit"));
    expect(result.current.status).toBe("failed");
    api.PUT.mockResolvedValueOnce(ok());
    await tick(AUTOSAVE_DELAY_MS);
    expect(result.current.status).toBe("saved");
    expect(api.PUT.mock.calls[1][1].body).toEqual({ body: "zweit" });
  });

  it("a network throw is a failure too, not a crash", async () => {
    api.PUT.mockRejectedValueOnce(new Error("offline"));
    const { result } = mount();
    act(() => result.current.schedule("offline"));
    await tick(AUTOSAVE_DELAY_MS);
    expect(result.current.status).toBe("failed");
  });
});

describe("discard and stale answers", () => {
  it("discard drops the draft and rests at idle; a late answer is stale", async () => {
    const gate = deferred();
    api.PUT.mockReturnValueOnce(gate.promise);
    const { result } = mount();
    act(() => result.current.schedule("weg damit"));
    let flushing!: Promise<string>;
    act(() => {
      flushing = result.current.flush();
    });
    await tick(0);
    act(() => result.current.discard());
    expect(result.current.status).toBe("idle");
    expect(getSaveStatus()).toBe("idle");
    gate.resolve(ok());
    let outcome!: string;
    await act(async () => {
      outcome = await flushing;
    });
    expect(outcome).toBe("stale");
    expect(result.current.status).toBe("idle");
  });
});

describe("the read family and the chrome seam", () => {
  it("a landed save invalidates the scenes key beside the shelf family", async () => {
    const spy = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = mount();
    act(() => result.current.schedule("Wörter"));
    await tick(AUTOSAVE_DELAY_MS);
    const keys = spy.mock.calls.map((call) => call[0]?.queryKey);
    expect(keys).toContainEqual(["scenes", CHAPTER]);
    expect(keys).toContainEqual(["chapters", NOVEL]);
    expect(keys).toContainEqual(["novels"]);
    expect(keys).toContainEqual(["activity"]);
    spy.mockRestore();
  });

  it("the store mirrors the live state and rests at idle when the hook goes away", async () => {
    const { result, unmount } = mount();
    act(() => result.current.schedule("Spiegel"));
    expect(getSaveStatus()).toBe("saving");
    await tick(AUTOSAVE_DELAY_MS);
    expect(getSaveStatus()).toBe("saved");
    unmount();
    expect(getSaveStatus()).toBe("idle");
  });

  it("a hidden tab flushes the pending body now — a visible one does not", async () => {
    const { result } = mount();
    act(() => result.current.schedule("Tab weg"));
    expect(api.PUT).not.toHaveBeenCalled();
    // A visible tab's visibilitychange must not force the flush.
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    expect(api.PUT).not.toHaveBeenCalled();
    // The tab goes hidden: the pending body flushes at once.
    Object.defineProperty(document, "visibilityState", { value: "hidden", configurable: true });
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    expect(api.PUT).toHaveBeenCalledTimes(1);
    expect(api.PUT.mock.calls[0][1].body).toEqual({ body: "Tab weg" });
    delete (document as { visibilityState?: unknown }).visibilityState;
  });
});
