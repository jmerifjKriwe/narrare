/**
 * KBAssistedCreationFooter tests — footer for assisted KB creation.
 *
 * Tests:
 * 1. Renders entry name input
 * 2. Renders action buttons (interview, enhance, cancel, save)
 * 3. Calls setEntryName on input change
 * 4. Calls setView with 'interview' when interview button clicked
 * 5. Calls setView with 'enhance' when enhance button clicked
 * 6. Calls onCancel when cancel clicked
 * 7. Calls onCompleteAndSave when save clicked
 * 8. Disables enhance when filledFields=0
 * 9. Disables save when entryName is empty
 * 10. Hides name input when session is complete
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { KBAssistedCreationFooter } from "@/components/studio/kb/KBAssistedCreationFooter";
import type { AssistedView } from "@/components/studio/kb/KBAssistedCreationPanel";
import type { KBCreationSession } from "@/lib/api/kb-sessions";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function createSession(overrides: Partial<KBCreationSession> = {}): KBCreationSession {
  return {
    id: "session-1",
    novel_id: "novel-1",
    user_id: "user-1",
    entity_type: "character",
    status: "active",
    fields: [],
    context_entries: [],
    name: undefined,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

const defaultView: AssistedView = "fields";

const defaultProps = {
  session: createSession(),
  entryName: "Anna",
  setEntryName: vi.fn(),
  view: defaultView,
  setView: vi.fn(),
  filledFields: 3,
  completePending: false,
  onCancel: vi.fn(),
  onCompleteAndSave: vi.fn(),
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("KBAssistedCreationFooter", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders entry name input", () => {
    render(<KBAssistedCreationFooter {...defaultProps} />);

    expect(screen.getByText("kb.entry_name")).toBeDefined();
    expect(screen.getByDisplayValue("Anna")).toBeDefined();
  });

  it("renders interview button", () => {
    render(<KBAssistedCreationFooter {...defaultProps} />);

    expect(screen.getByText("kb.startInterview")).toBeDefined();
  });

  it("renders enhance button", () => {
    render(<KBAssistedCreationFooter {...defaultProps} />);

    expect(screen.getByText("kb.enhanceAll")).toBeDefined();
  });

  it("renders cancel button", () => {
    render(<KBAssistedCreationFooter {...defaultProps} />);

    expect(screen.getByText("kb.cancel")).toBeDefined();
  });

  it("renders save button", () => {
    render(<KBAssistedCreationFooter {...defaultProps} />);

    expect(screen.getByText("kb.completeAndSave")).toBeDefined();
  });

  it("calls setEntryName on input change", () => {
    const setEntryName = vi.fn();
    render(<KBAssistedCreationFooter {...defaultProps} setEntryName={setEntryName} />);

    const input = screen.getByDisplayValue("Anna");
    fireEvent.change(input, { target: { value: "Johann" } });

    expect(setEntryName).toHaveBeenCalledWith("Johann");
  });

  it("calls setView with 'interview' when interview button clicked", () => {
    const setView = vi.fn();
    render(<KBAssistedCreationFooter {...defaultProps} setView={setView} />);

    fireEvent.click(screen.getByText("kb.startInterview"));
    expect(setView).toHaveBeenCalledWith("interview");
  });

  it("calls setView with 'enhance' when enhance button clicked", () => {
    const setView = vi.fn();
    render(<KBAssistedCreationFooter {...defaultProps} setView={setView} />);

    fireEvent.click(screen.getByText("kb.enhanceAll"));
    expect(setView).toHaveBeenCalledWith("enhance");
  });

  it("calls onCancel when cancel clicked", () => {
    const onCancel = vi.fn();
    render(<KBAssistedCreationFooter {...defaultProps} onCancel={onCancel} />);

    fireEvent.click(screen.getByText("kb.cancel"));
    expect(onCancel).toHaveBeenCalled();
  });

  it("calls onCompleteAndSave when save clicked", () => {
    const onCompleteAndSave = vi.fn();
    render(<KBAssistedCreationFooter {...defaultProps} onCompleteAndSave={onCompleteAndSave} />);

    fireEvent.click(screen.getByText("kb.completeAndSave"));
    expect(onCompleteAndSave).toHaveBeenCalled();
  });

  it("disables enhance button when filledFields=0", () => {
    render(<KBAssistedCreationFooter {...defaultProps} filledFields={0} />);

    const enhanceBtn = screen.getByText("kb.enhanceAll").closest("button")!;
    expect(enhanceBtn.disabled).toBe(true);
  });

  it("disables save button when entryName is empty", () => {
    render(<KBAssistedCreationFooter {...defaultProps} entryName="" />);

    const saveBtn = screen.getByText("kb.completeAndSave").closest("button")!;
    expect(saveBtn.disabled).toBe(true);
  });

  it("hides name input when session status is complete", () => {
    render(
      <KBAssistedCreationFooter
        {...defaultProps}
        session={createSession({ status: "complete" })}
      />,
    );

    expect(screen.queryByText("kb.entry_name")).toBeNull();
  });

  it("shows saving text when completePending=true", () => {
    render(<KBAssistedCreationFooter {...defaultProps} completePending />);

    expect(screen.getByText("kb.saving")).toBeDefined();
  });

  // CR-07 §16 regression guards: no hardcoded English visible fallbacks.
  it("does not render English 'Entry Name' label or placeholder fallbacks", () => {
    render(<KBAssistedCreationFooter {...defaultProps} />);

    expect(screen.queryByText("Entry Name")).toBeNull();
    expect(screen.queryByPlaceholderText("Enter a name for your entry")).toBeNull();
  });

  it("does not render English 'Saving...' fallback when completePending", () => {
    render(<KBAssistedCreationFooter {...defaultProps} completePending />);

    expect(screen.queryByText("Saving...")).toBeNull();
  });
});
