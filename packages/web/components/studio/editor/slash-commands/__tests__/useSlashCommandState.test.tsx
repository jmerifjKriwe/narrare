/**
 * useSlashCommandState integration tests (CR-AUFG-07-20).
 *
 * Mounts a real TipTap editor + the hook + the menu and drives typing to verify
 * the spec's conflict / prose guarantees:
 *  - `/` opens the menu in an empty paragraph.
 *  - `/rew` filters.
 *  - Escape dismisses and the `/` stays as prose (not deleted).
 *  - selecting a command deletes the `/query` and dispatches.
 *  - typing a space after `/` closes the menu and keeps prose (no conflict).
 */

import { act, render, screen, waitFor } from "@testing-library/react";
import Placeholder from "@tiptap/extension-placeholder";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { beforeAll, describe, expect, it, vi } from "vitest";
import type { SlashCommandDispatchContext } from "../contracts";
import { AI_SLASH_COMMANDS } from "../registry";
import { SlashCommandMenu } from "../SlashCommandMenu";
import { useSlashCommandState } from "../useSlashCommandState";

const t = (key: string) => key;

let captured: {
  editor: ReturnType<typeof useEditor>;
  state: ReturnType<typeof useSlashCommandState>;
};
const ALL_OPS = new Set(AI_SLASH_COMMANDS.map((c) => c.operationId));

function Harness({
  dispatchContext,
  wiredOps = ALL_OPS,
}: {
  dispatchContext: SlashCommandDispatchContext;
  wiredOps?: ReadonlySet<string>;
}) {
  const editor = useEditor({
    immediatelyRender: false,
    extensions: [StarterKit, Placeholder.configure({ placeholder: "p" })],
    content: "<p></p>",
  });
  const state = useSlashCommandState({
    editor,
    commands: AI_SLASH_COMMANDS,
    dispatchContext,
    wiredOps,
    t,
  });
  captured = { editor, state } as never;
  return (
    <>
      <EditorContent editor={editor} />
      {state.open && (
        <SlashCommandMenu
          items={state.items}
          activeIndex={state.activeIndex}
          query={state.query}
          position={state.position}
          onActiveIndexChange={state.setActiveIndex}
          onSelect={state.selectIndex}
          onDismiss={state.dismiss}
          t={t}
        />
      )}
      <div data-testid="probe">{state.open ? `open:${state.query}` : "closed"}</div>
    </>
  );
}

beforeAll(() => {
  if (typeof document.elementFromPoint !== "function") {
    document.elementFromPoint = vi.fn(() => null);
  }
});

async function openMenuWith(dispatchContext: SlashCommandDispatchContext) {
  render(<Harness dispatchContext={dispatchContext} />);
  await waitFor(() => expect(captured.editor).toBeTruthy());
  const editor = captured.editor!;
  act(() => {
    editor!.chain().focus().insertContent("/").run();
  });
  await waitFor(() => {
    expect(screen.getByTestId("probe").textContent).toBe("open:");
  });
  return editor;
}

describe("useSlashCommandState — detection & filtering", () => {
  it("opens the menu when `/` is typed at the start of an empty paragraph", async () => {
    await openMenuWith({
      rewriteSelection: vi.fn(),
      continueWriting: vi.fn(),
      generateDraft: vi.fn(),
      coAuthorSelection: vi.fn(),
      askChat: vi.fn(),
      explainSelection: vi.fn(),
    });
    expect(screen.getByRole("listbox")).toBeInTheDocument();
  });

  it("filters commands as the user types a query", async () => {
    const editor = await openMenuWith({
      rewriteSelection: vi.fn(),
      continueWriting: vi.fn(),
      generateDraft: vi.fn(),
      coAuthorSelection: vi.fn(),
      askChat: vi.fn(),
      explainSelection: vi.fn(),
    });
    act(() => {
      editor.chain().insertContent("rew").run();
    });
    await waitFor(() => {
      expect(screen.getByTestId("probe").textContent).toBe("open:rew");
    });
    // only the rewrite command should be listed
    expect(screen.getByText("slashCommands.rewrite.label")).toBeInTheDocument();
    expect(screen.queryByText("slashCommands.continue.label")).toBeNull();
  });
});

describe("useSlashCommandState — prose & escape guarantees", () => {
  it("Escape dismisses the menu but leaves the `/` as prose", async () => {
    const editor = await openMenuWith({
      rewriteSelection: vi.fn(),
      continueWriting: vi.fn(),
      generateDraft: vi.fn(),
      coAuthorSelection: vi.fn(),
      askChat: vi.fn(),
      explainSelection: vi.fn(),
    });
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    });
    await waitFor(() => {
      expect(screen.getByTestId("probe").textContent).toBe("closed");
    });
    // the slash must remain in the document as normal prose
    expect(editor.getText()).toBe("/");
  });

  it("typing a space after `/` closes the menu and keeps prose (no shortcut conflict)", async () => {
    const editor = await openMenuWith({
      rewriteSelection: vi.fn(),
      continueWriting: vi.fn(),
      generateDraft: vi.fn(),
      coAuthorSelection: vi.fn(),
      askChat: vi.fn(),
      explainSelection: vi.fn(),
    });
    act(() => {
      editor.chain().insertContent(" hello").run();
    });
    await waitFor(() => {
      expect(screen.getByTestId("probe").textContent).toBe("closed");
    });
    // `/ hello` stays as prose — the slash was not consumed
    expect(editor.getText().replace(/\u00a0/g, " ")).toContain("/ hello");
  });

  it("does NOT open when `/` is typed mid-paragraph", async () => {
    render(
      <Harness
        dispatchContext={{
          rewriteSelection: vi.fn(),
          continueWriting: vi.fn(),
          generateDraft: vi.fn(),
          coAuthorSelection: vi.fn(),
          askChat: vi.fn(),
          explainSelection: vi.fn(),
        }}
      />,
    );
    await waitFor(() => expect(captured.editor).toBeTruthy());
    const editor = captured.editor!;
    act(() => {
      editor.chain().focus().insertContent("hello world ").run();
    });
    act(() => {
      editor.chain().insertContent("/").run();
    });
    // menu should remain closed because `/` is not at paragraph start
    expect(screen.getByTestId("probe").textContent).toBe("closed");
  });
});

describe("useSlashCommandState — dispatch", () => {
  it("selecting a command deletes the `/query` and routes to the dispatch context", async () => {
    const dispatchContext: SlashCommandDispatchContext = {
      rewriteSelection: vi.fn(),
      continueWriting: vi.fn(),
      generateDraft: vi.fn(),
      coAuthorSelection: vi.fn(),
      askChat: vi.fn(),
      explainSelection: vi.fn(),
    };
    const editor = await openMenuWith(dispatchContext);
    // type `co` → coauthor is not a prefix match, but `draft`/`chat`... use `cont`
    act(() => {
      editor.chain().insertContent("cont").run();
    });
    await waitFor(() => {
      expect(screen.getByTestId("probe").textContent).toBe("open:cont");
    });
    act(() => {
      captured.state.selectIndex(0);
    });
    await waitFor(() => {
      expect(screen.getByTestId("probe").textContent).toBe("closed");
    });
    expect(dispatchContext.continueWriting).toHaveBeenCalledOnce();
    // the `/cont` text must have been removed from the document
    expect(editor.getText()).toBe("");
  });

  it("does not dispatch a disabled (unavailable) command", async () => {
    const dispatchContext: SlashCommandDispatchContext = {
      rewriteSelection: vi.fn(),
      continueWriting: vi.fn(),
      generateDraft: vi.fn(),
      coAuthorSelection: vi.fn(),
      askChat: vi.fn(),
      explainSelection: vi.fn(),
    };
    // continue operation not wired → command unavailable
    const noContinue = new Set(ALL_OPS);
    noContinue.delete("writing.continue");
    render(<Harness dispatchContext={dispatchContext} wiredOps={noContinue} />);
    await waitFor(() => expect(captured.editor).toBeTruthy());
    const editor = captured.editor!;
    act(() => {
      editor.chain().focus().insertContent("/cont").run();
    });
    await waitFor(() => {
      expect(screen.getByTestId("probe").textContent).toBe("open:cont");
    });
    // the continue item is the only match and is unavailable
    expect(screen.getByText("slashCommands.continue.label")).toBeInTheDocument();
    act(() => {
      captured.state.selectIndex(0);
    });
    expect(dispatchContext.continueWriting).not.toHaveBeenCalled();
  });
});
