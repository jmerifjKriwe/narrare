/**
 * EditorWorkspace slash-wiring tests — audits B08 (/continue) + B09 (/coauthor).
 *
 * EditorWorkspace passed no `slashCommandHandlers`, so TipTapEditor rendered
 * the continue + coauthor slash items "unavailable" and the CoAuthorPanel
 * had no trigger. The workspace now forwards the host handlers.
 *
 * @module EditorWorkspace.slash.test
 */

import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { EditorWorkspace } from "../EditorWorkspace";
import type { EditorSurfaceProps } from "../types";

const TipTapEditor = vi.hoisted(() => vi.fn(() => null));

// The hoisted spy is exposed directly (no plain wrapper) so that
// `vi.mocked(...)` in the assertions below sees the real call history.
vi.mock("../../TipTapEditor", () => ({
  TipTapEditor: TipTapEditor,
}));

import { TipTapEditor as TipTapEditorMock } from "../../TipTapEditor";

const baseProps: EditorSurfaceProps = {
  editor: null,
  novelId: "novel-1",
  activeChapterId: "chapter-1",
  content: "<p>Some prose</p>",
  setContent: vi.fn(),
  handleAutosave: vi.fn(async () => {}),
};

describe("EditorWorkspace slash wiring", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("forwards slashCommandHandlers to TipTapEditor (B08/B09)", () => {
    const onContinue = vi.fn();
    const onCoAuthor = vi.fn();
    render(<EditorWorkspace {...baseProps} slashCommandHandlers={{ onContinue, onCoAuthor }} />);

    expect(TipTapEditorMock).toHaveBeenCalled();
    const passed = vi.mocked(TipTapEditorMock).mock.calls[0][0];
    expect(passed.slashCommandHandlers?.onContinue).toBe(onContinue);
    expect(passed.slashCommandHandlers?.onCoAuthor).toBe(onCoAuthor);
  });

  it("omits the prop when the host provides none (backwards compatible)", () => {
    render(<EditorWorkspace {...baseProps} />);
    const passed = vi.mocked(TipTapEditorMock).mock.calls[0][0];
    expect(passed.slashCommandHandlers).toBeUndefined();
  });
});
