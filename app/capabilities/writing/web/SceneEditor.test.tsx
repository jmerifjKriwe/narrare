// @vitest-environment jsdom
/**
 * The scene editor (W4 Task 12) — the TipTap prose surface that replaces the
 * read-only paragraphs: a real labelled textbox, the body's paragraphs with
 * the draft's drop cap on the first, and a plain-text storage contract (the
 * scene body is prose, not Markdown — paragraphs joined by a blank line,
 * hard breaks by a single newline, the same shape the read-only port drew
 * and the server's whitespace rule counts). Content initializes once per
 * scene; a switch remounts (the page keys it), never resets a live caret.
 *
 * Task 16 adds the ghost layer: the continuation's three faces at the scene
 * tail (KACHEL 7's streaming chrome, the light draft's pending preview with
 * the [Tab] keycap pill, KACHEL 8's corrected error face), the keyboard
 * contract (Tab accepts from the prose, Esc dismisses BEFORE the leave
 * guard's own Esc) and the autosave handoff (the insertion rides onChange,
 * the one write path). The proposal's arrival is announced once, AT the
 * streaming→pending transition, through the editor's hidden live region —
 * a region mounted populated never speaks, so the preview wears no role.
 */
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { Editor } from "@tiptap/core";
import { useEffect, useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { client } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { applyLocale } from "@shell/lib/locale";

import { SceneEditor, bodyToHtml } from "./SceneEditor";
import { LeaveGuardDialog } from "./WorkspaceStates";
import { useAutosave, AUTOSAVE_DELAY_MS } from "./useAutosave";
import type { Continuation, ContinuationPhase } from "./workspace";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

const de = catalogs.de;
const api = client as unknown as { PUT: ReturnType<typeof vi.fn> };

// jsdom lays out nothing: ProseMirror reads Range rects when it scrolls a
// selection into view (the focus the streaming start and the acceptance
// command). Hand it the zeros the elements claim (the page test's own
// polyfill).
const zeroRect = { top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0, x: 0, y: 0 } as DOMRect;
Range.prototype.getClientRects = function (): DOMRectList {
  return [zeroRect] as unknown as DOMRectList;
};
Range.prototype.getBoundingClientRect = () => zeroRect;

beforeEach(() => {
  applyLocale("de");
});

afterEach(() => {
  cleanup();
});

/** Wait for the live instance (the editor mounts in an effect). */
async function editorOf(get: () => Editor | null): Promise<Editor> {
  await waitFor(() => {
    expect(get()).not.toBeNull();
  });
  return get() as Editor;
}

describe("bodyToHtml — the plain prose the editor initializes from", () => {
  it("blank lines separate paragraphs, single newlines are hard breaks", () => {
    expect(bodyToHtml("Erster Absatz.\n\nZweiter Absatz.")).toBe(
      "<p>Erster Absatz.</p><p>Zweiter Absatz.</p>",
    );
    expect(bodyToHtml("Zeile eins\nZeile zwei")).toBe("<p>Zeile eins<br>Zeile zwei</p>");
  });

  it("an empty body is one empty paragraph — no invented prose", () => {
    expect(bodyToHtml("")).toBe("<p></p>");
    expect(bodyToHtml("   \n\n  ")).toBe("<p></p>");
  });

  it("escapes the markup characters prose may carry", () => {
    expect(bodyToHtml("<x> & y")).toBe("<p>&lt;x&gt; &amp; y</p>");
  });
});

describe("the editing surface", () => {
  it("is a real labelled multiline textbox wearing the live prose class", async () => {
    render(<SceneEditor body="Ein Satz." onChange={() => {}} label="Szenenprosa" />);
    await screen.findByRole("textbox", { name: "Szenenprosa" });
    await waitFor(() => expect(screen.getByRole("textbox").textContent).toBe("Ein Satz."));
    const box = screen.getByRole("textbox");
    expect(box.getAttribute("aria-multiline")).toBe("true");
    expect(box.closest(".workspace-prose-live")).not.toBeNull();
  });

  it("renders the body's paragraphs, the first under the drop cap", async () => {
    render(
      <SceneEditor body={"Erster Absatz.\n\nZweiter Absatz."} onChange={() => {}} label="Prosa" />,
    );
    await screen.findByRole("textbox");
    await waitFor(() => expect(screen.getByRole("textbox").querySelectorAll("p")).toHaveLength(2));
    const box = screen.getByRole("textbox");
    const paragraphs = box.querySelectorAll("p");
    expect(paragraphs[0].textContent).toBe("Erster Absatz.");
    expect(paragraphs[1].textContent).toBe("Zweiter Absatz.");
    // The drop cap is the wrapper's first-paragraph rule (globals.css).
    expect(box.className).toContain("ProseMirror");
  });

  it("an empty body keeps the surface honest — one empty paragraph", async () => {
    render(<SceneEditor body="" onChange={() => {}} label="Prosa" />);
    await screen.findByRole("textbox");
    await waitFor(() => expect(screen.getByRole("textbox").querySelectorAll("p")).toHaveLength(1));
    expect(screen.getByRole("textbox").textContent).toBe("");
  });

  it("every edit emits the whole body as plain prose — paragraphs by blank line", async () => {
    const onChange = vi.fn();
    let instance: Editor | null = null;
    render(
      <SceneEditor
        body="Alt."
        onChange={onChange}
        label="Prosa"
        onReady={(editor) => {
          instance = editor;
        }}
      />,
    );
    const editor = await editorOf(() => instance);
    expect(onChange).not.toHaveBeenCalled();
    editor.commands.insertContentAt(
      { from: 0, to: editor.state.doc.content.size },
      "<p>Neu eins.</p><p>Neu zwei.</p>",
    );
    expect(onChange).toHaveBeenLastCalledWith("Neu eins.\n\nNeu zwei.");
  });

  it("a hard break serializes as a single newline, not a paragraph gap", async () => {
    const onChange = vi.fn();
    let instance: Editor | null = null;
    render(
      <SceneEditor
        body="Alt."
        onChange={onChange}
        label="Prosa"
        onReady={(editor) => {
          instance = editor;
        }}
      />,
    );
    const editor = await editorOf(() => instance);
    editor.commands.insertContentAt(
      { from: 0, to: editor.state.doc.content.size },
      "<p>Zeile eins<br>Zeile zwei</p>",
    );
    expect(onChange).toHaveBeenLastCalledWith("Zeile eins\nZeile zwei");
  });

  it("initializes once — a body prop change does not reset the live document", async () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <SceneEditor body="Erst." onChange={onChange} label="Prosa" />,
    );
    await screen.findByRole("textbox");
    await waitFor(() => expect(screen.getByRole("textbox").textContent).toBe("Erst."));
    // The cache refetch after a save hands the saved body back; the editor
    // keeps its own live content (the page keys it per scene for a swap).
    rerender(<SceneEditor body="Erst." onChange={onChange} label="Prosa" />);
    expect(screen.getByRole("textbox").textContent).toBe("Erst.");
    expect(onChange).not.toHaveBeenCalled();
  });

  it("a scene switch remounts with the new body — the content swap", async () => {
    const { rerender } = render(
      <SceneEditor key="s1" body="Szene eins." onChange={() => {}} label="Prosa" />,
    );
    await screen.findByRole("textbox");
    await waitFor(() => expect(screen.getByRole("textbox").textContent).toBe("Szene eins."));
    // The page keys the editor by scene id: a new key is a new document.
    rerender(<SceneEditor key="s2" body="Szene zwei." onChange={() => {}} label="Prosa" />);
    await waitFor(() => expect(screen.getByRole("textbox").textContent).toBe("Szene zwei."));
  });
});

// --- The ghost layer (W4 Task 16) ------------------------------------------

const GHOST_TEXT = "Der Nebel hob sich vom See und legte sich über die Straße.";
const BODY = "Der Nebel kam von See.";

/** The continuation as a stateful stand-in: dismiss rests the ghost at idle
 *  exactly as the hook does, so the keyboard legs see the real precedence.
 *  onPhase hands the test the setter — the arrival legs drive the real
 *  streaming→pending transition, not a mounted-pending shortcut. */
function GhostHarness({
  body = BODY,
  initialPhase = "pending" as ContinuationPhase,
  text = GHOST_TEXT,
  onChange = () => {},
  onDismiss,
  onRetry,
  onPhase,
  guard = false,
  onStay = () => {},
}: {
  body?: string;
  initialPhase?: ContinuationPhase;
  text?: string;
  onChange?: (body: string) => void;
  onDismiss?: () => void;
  onRetry?: () => void;
  onPhase?: (setPhase: (phase: ContinuationPhase) => void) => void;
  guard?: boolean;
  onStay?: () => void;
}) {
  const [phase, setPhase] = useState<ContinuationPhase>(initialPhase);
  useEffect(() => {
    onPhase?.(setPhase);
  }, [onPhase]);
  const continuation: Continuation = {
    phase,
    text,
    errorCode: phase === "error" ? "network" : null,
    start: () => setPhase("streaming"),
    dismiss: () => {
      onDismiss?.();
      setPhase("idle");
    },
    retry: () => {
      onRetry?.();
      setPhase("streaming");
    },
  };
  return (
    <>
      <SceneEditor body={body} onChange={onChange} label="Szenenprosa" continuation={continuation} />
      {guard && <LeaveGuardDialog onStay={onStay} onDiscard={() => {}} />}
    </>
  );
}

describe("the ghost's streaming face — KACHEL 7", () => {
  it("the ARIA chip pulses over the accumulating preview, outside the document", async () => {
    render(<GhostHarness initialPhase="streaming" text="Der Nebel hob sich " />);
    await screen.findByRole("textbox");
    const ghost = screen.getByTestId("ghost-preview");
    // The chip is the preview's own status — the arrival region stands
    // empty beside it (two status roles while the stream runs).
    expect(ghost.querySelector('[role="status"]')?.textContent).toContain(
      de["writing.workspace.ghost.writing"],
    );
    expect(ghost.textContent).toContain("Der Nebel hob sich ");
    // The preview is italic and wears the writing area's ink (the /70 draft
    // tone fails the AA floor on both themes — the ink rides full strength,
    // the wash carries the softness; the amber pill's own discipline).
    const preview = ghost.querySelector("p");
    expect(preview?.className).toContain("italic");
    expect(preview?.className).toContain("text-area-writing");
    // The ghost is NOT the scene's words: the textbox holds the body alone.
    expect(screen.getByRole("textbox").textContent).toBe(BODY);
  });

  it("the streaming start moves the caret to the prose — Tab's seat", async () => {
    render(<GhostHarness initialPhase="streaming" />);
    const box = await screen.findByRole("textbox");
    await waitFor(() => expect(document.activeElement).toBe(box));
  });
});

describe("the ghost's pending face — the light draft's preview + keycap pill", () => {
  it("stands at the tail with the [Tab] pill, outside the document", async () => {
    render(<GhostHarness />);
    await screen.findByRole("textbox");
    const ghost = screen.getByTestId("ghost-preview");
    expect(ghost.textContent).toContain(GHOST_TEXT);
    const pill = screen.getByRole("button", { name: /Vorschlag übernehmen/ });
    expect(pill.textContent).toContain("Tab");
    expect(pill.getAttribute("aria-keyshortcuts")).toBe("Tab");
    expect(screen.getByRole("textbox").textContent).toBe(BODY);
  });

  it("the pill accepts: the proposal joins the tail as a new paragraph", async () => {
    const onChange = vi.fn();
    const onDismiss = vi.fn();
    render(<GhostHarness onChange={onChange} onDismiss={onDismiss} />);
    await screen.findByRole("textbox");
    fireEvent.click(screen.getByRole("button", { name: /Vorschlag übernehmen/ }));
    expect(onDismiss).toHaveBeenCalled();
    expect(onChange).toHaveBeenLastCalledWith(`${BODY}\n\n${GHOST_TEXT}`);
    expect(screen.getByRole("textbox").textContent).toBe(BODY + GHOST_TEXT);
    expect(screen.queryByTestId("ghost-preview")).toBeNull();
  });

  it("Tab in the prose accepts — the keyboard's own door", async () => {
    const onChange = vi.fn();
    render(<GhostHarness onChange={onChange} />);
    const box = await screen.findByRole("textbox");
    box.focus();
    fireEvent.keyDown(box, { key: "Tab" });
    expect(onChange).toHaveBeenLastCalledWith(`${BODY}\n\n${GHOST_TEXT}`);
    expect(screen.queryByTestId("ghost-preview")).toBeNull();
  });

  it("Tab outside the prose keeps its native meaning — focus moves, nothing inserts", async () => {
    const onChange = vi.fn();
    render(
      <>
        <GhostHarness onChange={onChange} />
        <button type="button">Anderswo</button>
      </>,
    );
    await screen.findByRole("textbox");
    const other = screen.getByRole("button", { name: "Anderswo" });
    other.focus();
    fireEvent.keyDown(other, { key: "Tab" });
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByTestId("ghost-preview")).not.toBeNull();
  });

  it("an empty scene takes the proposal alone — no leading paragraph gap", async () => {
    const onChange = vi.fn();
    render(<GhostHarness body="" onChange={onChange} />);
    const box = await screen.findByRole("textbox");
    box.focus();
    fireEvent.keyDown(box, { key: "Tab" });
    expect(onChange).toHaveBeenLastCalledWith(GHOST_TEXT);
  });

  it("a multi-paragraph proposal keeps its own structure", async () => {
    const onChange = vi.fn();
    render(<GhostHarness text={"Erster Vorschlag.\n\nZweiter Vorschlag."} onChange={onChange} />);
    const box = await screen.findByRole("textbox");
    box.focus();
    fireEvent.keyDown(box, { key: "Tab" });
    expect(onChange).toHaveBeenLastCalledWith(`${BODY}\n\nErster Vorschlag.\n\nZweiter Vorschlag.`);
  });

  it("a multi-paragraph proposal previews with the SAME breaks it inserts on Tab", async () => {
    const onChange = vi.fn();
    const proposal = "Erster Vorschlag.\n\nZweiter Vorschlag.\nMit harter Zeile.";
    render(<GhostHarness text={proposal} onChange={onChange} />);
    const box = await screen.findByRole("textbox");
    // The preview draws the acceptance path's own structure (proseBlocks —
    // bodyToHtml's split): two paragraphs, the second with the hard break.
    const preview = screen.getByTestId("ghost-preview").querySelectorAll("p");
    expect(preview).toHaveLength(2);
    expect(preview[0].textContent).toBe("Erster Vorschlag.");
    expect(preview[1].querySelectorAll("br")).toHaveLength(1);
    expect(preview[1].textContent).toContain("Zweiter Vorschlag.");
    expect(preview[1].textContent).toContain("Mit harter Zeile.");
    // The pill rides inline after the LAST paragraph — the one-block geometry.
    const pill = screen.getByRole("button", { name: /Vorschlag übernehmen/ });
    expect(preview[1].contains(pill)).toBe(true);

    box.focus();
    fireEvent.keyDown(box, { key: "Tab" });
    expect(onChange).toHaveBeenLastCalledWith(
      `${BODY}\n\nErster Vorschlag.\n\nZweiter Vorschlag.\nMit harter Zeile.`,
    );
    // The inserted document carries the very breaks the preview drew: the
    // body's own paragraph plus the proposal's two, the hard break intact.
    const inserted = screen.getByRole("textbox").querySelectorAll("p");
    expect(inserted).toHaveLength(3);
    expect(inserted[1].textContent).toBe("Erster Vorschlag.");
    expect(inserted[2].querySelectorAll("br")).toHaveLength(1);
    expect(inserted[2].textContent).toBe("Zweiter Vorschlag.Mit harter Zeile.");
  });

  it("the preview trims and drops blank blocks exactly as the insertion does", async () => {
    const onChange = vi.fn();
    render(<GhostHarness text={"  Erster.\n\n \n\nZweiter.  "} onChange={onChange} />);
    const box = await screen.findByRole("textbox");
    // The whitespace-only block is no paragraph — the shared split's rule.
    const preview = screen.getByTestId("ghost-preview").querySelectorAll("p");
    expect(preview).toHaveLength(2);
    expect(preview[0].textContent).toBe("Erster.");
    box.focus();
    fireEvent.keyDown(box, { key: "Tab" });
    expect(onChange).toHaveBeenLastCalledWith(`${BODY}\n\nErster.\n\nZweiter.`);
  });
});

describe("the pending arrival — the hidden region speaks at the transition", () => {
  it("streaming → pending fills the hidden status; the preview itself wears no role", async () => {
    let land: (() => void) | undefined;
    render(
      <GhostHarness initialPhase="streaming" onPhase={(set) => { land = () => set("pending"); }} />,
    );
    await screen.findByRole("textbox");
    const live = screen.getByTestId("ghost-announcement");
    expect(live.getAttribute("role")).toBe("status");
    expect(live.className).toContain("sr-only");
    // Mounted empty: a live region announces changes, not initial content.
    expect(live.textContent).toBe("");
    act(() => {
      land?.();
    });
    expect(screen.getByTestId("ghost-preview")).not.toBeNull();
    expect(live.textContent).toBe(de["writing.workspace.ghost.ready"]);
    // The visible proposal is no live region — the hidden one speaks.
    expect(screen.getByTestId("ghost-preview").querySelector('[role="status"]')).toBeNull();
  });

  it("a pending face mounted without a stream stays silent — no transition, no words", async () => {
    render(<GhostHarness />);
    await screen.findByRole("textbox");
    expect(screen.getByTestId("ghost-announcement").textContent).toBe("");
  });

  it("the streaming and error faces leave the region empty — only the arrival speaks", async () => {
    const { unmount } = render(<GhostHarness initialPhase="streaming" />);
    await screen.findByRole("textbox");
    expect(screen.getByTestId("ghost-announcement").textContent).toBe("");
    unmount();
    render(<GhostHarness initialPhase="error" />);
    await screen.findByRole("textbox");
    expect(screen.getByTestId("ghost-announcement").textContent).toBe("");
  });

  it("leaving pending clears the region — the next arrival speaks again", async () => {
    let setPhase: ((phase: ContinuationPhase) => void) | undefined;
    render(<GhostHarness initialPhase="streaming" onPhase={(set) => { setPhase = set; }} />);
    const box = await screen.findByRole("textbox");
    act(() => {
      setPhase?.("pending");
    });
    const live = screen.getByTestId("ghost-announcement");
    expect(live.textContent).toBe(de["writing.workspace.ghost.ready"]);
    fireEvent.keyDown(box, { key: "Escape" });
    expect(live.textContent).toBe("");
    // The identical words, a second time: a change again, not a silence.
    act(() => {
      setPhase?.("streaming");
    });
    act(() => {
      setPhase?.("pending");
    });
    expect(live.textContent).toBe(de["writing.workspace.ghost.ready"]);
  });
});

describe("Esc — the ghost owns it first", () => {
  it("dismisses the pending ghost", async () => {
    const onDismiss = vi.fn();
    render(<GhostHarness onDismiss={onDismiss} />);
    const box = await screen.findByRole("textbox");
    fireEvent.keyDown(box, { key: "Escape" });
    expect(onDismiss).toHaveBeenCalled();
    expect(screen.queryByTestId("ghost-preview")).toBeNull();
  });

  it("dismisses the streaming ghost too — a chosen stop, no error face", async () => {
    const onDismiss = vi.fn();
    render(<GhostHarness initialPhase="streaming" onDismiss={onDismiss} />);
    const box = await screen.findByRole("textbox");
    fireEvent.keyDown(box, { key: "Escape" });
    expect(onDismiss).toHaveBeenCalled();
    expect(screen.queryByTestId("ghost-preview")).toBeNull();
    expect(screen.queryByTestId("ghost-error")).toBeNull();
  });

  it("dismisses the error face too — Esc clears it", async () => {
    const onDismiss = vi.fn();
    render(<GhostHarness initialPhase="error" onDismiss={onDismiss} />);
    const box = await screen.findByRole("textbox");
    fireEvent.keyDown(box, { key: "Escape" });
    expect(onDismiss).toHaveBeenCalled();
    expect(screen.queryByTestId("ghost-error")).toBeNull();
  });

  it("stands BEFORE the leave guard: Esc drops the ghost, the guard stays", async () => {
    const onDismiss = vi.fn();
    const onStay = vi.fn();
    render(<GhostHarness guard onDismiss={onDismiss} onStay={onStay} />);
    await screen.findByRole("textbox");
    const stay = screen.getByRole("button", { name: de["writing.workspace.guard.stay"] });
    // The guard holds focus (its own opening rule); Esc lands there.
    fireEvent.keyDown(stay, { key: "Escape" });
    expect(onDismiss).toHaveBeenCalled();
    expect(onStay).not.toHaveBeenCalled();
    expect(screen.getByRole("alertdialog")).not.toBeNull();
    expect(screen.queryByTestId("ghost-preview")).toBeNull();
    // The ghost is gone: the next Esc is the guard's own — Bleiben.
    fireEvent.keyDown(stay, { key: "Escape" });
    expect(onStay).toHaveBeenCalledTimes(1);
  });

  it("no ghost, no interception — the guard's Esc works as before", async () => {
    const onStay = vi.fn();
    render(<GhostHarness initialPhase="idle" guard onStay={onStay} />);
    await screen.findByRole("textbox");
    const stay = screen.getByRole("button", { name: de["writing.workspace.guard.stay"] });
    fireEvent.keyDown(stay, { key: "Escape" });
    expect(onStay).toHaveBeenCalledTimes(1);
  });
});

describe("the ghost's error face — KACHEL 8, the corrected copy", () => {
  it("names the failure calmly: the Grund chip, the title, the reassurance, the two doors", async () => {
    render(<GhostHarness initialPhase="error" />);
    await screen.findByRole("textbox");
    const face = screen.getByRole("alert");
    expect(face.textContent).toContain(de["writing.workspace.ghost.errorChip"]);
    expect(face.textContent).toContain(de["writing.workspace.ghost.errorTitle"]);
    expect(face.textContent).toContain(de["writing.workspace.ghost.errorBody"]);
    // The body stays untouched — the reassurance is true.
    expect(screen.getByRole("textbox").textContent).toBe(BODY);
    expect(screen.getByRole("button", { name: de["writing.workspace.ghost.retry"] })).not.toBeNull();
    expect(screen.getByRole("button", { name: de["writing.workspace.ghost.discard"] })).not.toBeNull();
  });

  it("Erneut versuchen re-runs the ask; Verwerfen clears the face", async () => {
    const onRetry = vi.fn();
    const onDismiss = vi.fn();
    const { unmount } = render(<GhostHarness initialPhase="error" onRetry={onRetry} onDismiss={onDismiss} />);
    await screen.findByRole("textbox");
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.ghost.retry"] }));
    expect(onRetry).toHaveBeenCalled();
    // The retry stands the streaming face up again.
    expect(screen.getByTestId("ghost-preview")).not.toBeNull();
    unmount();

    render(<GhostHarness initialPhase="error" onDismiss={onDismiss} />);
    await screen.findByRole("textbox");
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.ghost.discard"] }));
    expect(onDismiss).toHaveBeenCalled();
    expect(screen.queryByTestId("ghost-error")).toBeNull();
  });
});

describe("the autosave handoff — Tab inserts, the one write path saves", () => {
  function HandoffHarness() {
    const autosave = useAutosave("s1", "c1", "n1");
    const [phase, setPhase] = useState<ContinuationPhase>("pending");
    const continuation: Continuation = {
      phase,
      text: GHOST_TEXT,
      errorCode: null,
      start: () => setPhase("streaming"),
      dismiss: () => setPhase("idle"),
      retry: () => setPhase("streaming"),
    };
    return (
      <SceneEditor
        body={BODY}
        label="Szenenprosa"
        continuation={continuation}
        onChange={(body) => {
          continuation.dismiss();
          autosave.schedule(body);
        }}
      />
    );
  }

  it("the accepted body rides the debounce into the scene's PUT", async () => {
    api.PUT.mockResolvedValue({ error: undefined, response: new Response(null, { status: 200 }) });
    render(<HandoffHarness />);
    const box = await screen.findByRole("textbox");
    await waitFor(() => expect(box.textContent).toBe(BODY));
    // The debounce is the autosave's own clock — fake it from here on.
    vi.useFakeTimers();
    try {
      box.focus();
      fireEvent.keyDown(box, { key: "Tab" });
      expect(api.PUT).not.toHaveBeenCalled();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(AUTOSAVE_DELAY_MS);
      });
      expect(api.PUT).toHaveBeenCalledWith("/api/writing/scenes/{scene_id}", {
        params: { path: { scene_id: "s1" } },
        body: { body: `${BODY}\n\n${GHOST_TEXT}` },
      });
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("the zen focus dimming (W4 Task 18) — the presets dim honestly", () => {
  const PARAGRAPHS = "Erster Absatz.\n\nZweiter Absatz.\n\nDritter Absatz.";

  async function mountWithFocus(focus: "paragraph" | "sentence" | "normal", body = PARAGRAPHS) {
    let instance: Editor | null = null;
    render(
      <SceneEditor
        body={body}
        label="Szenenprosa"
        focus={focus}
        onChange={() => {}}
        onReady={(editor) => {
          instance = editor;
        }}
      />,
    );
    const box = await screen.findByRole("textbox");
    const editor = await editorOf(() => instance);
    // The DOM text carries no paragraph gaps or hard breaks — the body's
    // own characters in order (the plain text minus every newline).
    await waitFor(() => expect(box.textContent).toBe(body.split("\n").join("")));
    return { box, editor };
  }

  it("paragraph focus: the caret's paragraph stands, the others dim — and it follows the caret", async () => {
    const { box, editor } = await mountWithFocus("paragraph");
    // The default selection sits at the document start — the first paragraph.
    await waitFor(() => {
      const paragraphs = box.querySelectorAll("p");
      expect(paragraphs[0].className).toContain("zen-active-block");
      expect(paragraphs[1].className).toContain("zen-dim-block");
      expect(paragraphs[2].className).toContain("zen-dim-block");
    });
    // Move the caret into the second paragraph — the dimming follows.
    act(() => {
      const insideSecond = editor.state.doc.child(0).nodeSize + 2;
      editor.commands.setTextSelection(insideSecond);
    });
    await waitFor(() => {
      const paragraphs = box.querySelectorAll("p");
      expect(paragraphs[0].className).toContain("zen-dim-block");
      expect(paragraphs[1].className).toContain("zen-active-block");
      expect(paragraphs[2].className).toContain("zen-dim-block");
    });
  });

  it("sentence focus: only the caret's sentence stands, across paragraph borders", async () => {
    const { box, editor } = await mountWithFocus("sentence", "Eins zwei. Drei vier.\n\nFünf sechs.");
    // Caret into the first paragraph's second sentence.
    act(() => {
      editor.commands.setTextSelection(12); // "Eins zwei. D|" — inside "Drei vier."
    });
    await waitFor(() => {
      const first = box.querySelectorAll("p")[0];
      const dimmed = first.querySelectorAll(".zen-dim-inline");
      expect(dimmed.length).toBeGreaterThan(0);
      expect(dimmed[0].textContent).toBe("Eins zwei. ");
    });
    const second = box.querySelectorAll("p")[1];
    expect(second.querySelector(".zen-dim-inline")?.textContent).toBe("Fünf sechs.");
    expect(box.querySelector(".zen-active-block")).toBeNull();
  });

  it("sentence focus reads across a hard break — the positions stay the document's own", async () => {
    const { box, editor } = await mountWithFocus("sentence", "Eins\nzwei. Drei vier.");
    act(() => {
      editor.commands.setTextSelection(13); // inside "Drei vier."
    });
    await waitFor(() => {
      const dimmed = box.querySelectorAll(".zen-dim-inline");
      expect(dimmed.length).toBeGreaterThan(0);
      expect(dimmed[0].textContent).toBe("Eins");
    });
    // The hard break itself is not text — the second line's fragment dims
    // as its own span, never swallowing the break.
    const dimmedTexts = [...box.querySelectorAll(".zen-dim-inline")].map((node) => node.textContent);
    expect(dimmedTexts).toContain("zwei. ");
    expect(box.textContent).toBe("Einszwei. Drei vier.");
  });

  it("normal focus dims nothing — and a mode change leaves the document untouched", async () => {
    const { box, editor } = await mountWithFocus("normal");
    expect(box.querySelector(".zen-dim-block")).toBeNull();
    expect(box.querySelector(".zen-dim-inline")).toBeNull();
    expect(box.querySelector(".zen-active-block")).toBeNull();
    expect(editor.getText()).toBe(PARAGRAPHS);
  });

  it("typing keeps the dimming live — the document change recomputes it", async () => {
    const { box, editor } = await mountWithFocus("paragraph");
    act(() => {
      editor.commands.insertContentAt(editor.state.doc.content.size, "<p>Vierter Absatz.</p>");
    });
    await waitFor(() => {
      const paragraphs = box.querySelectorAll("p");
      expect(paragraphs).toHaveLength(4);
      // The insertion leaves the caret in the new paragraph — it stands.
      expect(paragraphs[3].className).toContain("zen-active-block");
      expect(paragraphs[0].className).toContain("zen-dim-block");
    });
  });
});
