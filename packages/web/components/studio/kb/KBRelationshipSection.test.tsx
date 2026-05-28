/**
 * KBRelationshipSection tests
 *
 * Tests: renders relationships list, "no entries" when empty,
 * add relationship button opens dialog, delete triggers mutation.
 *
 * Mocking strategy:
 * - useKBEntries / useCreateKBRelationship / useDeleteKBRelationship: controlled
 *
 * next-intl is globally mocked in setupTests.ts (returns keys directly).
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { KBEntry, KBRelationship } from "@/lib/api/kb";
import { KBRelationshipSection } from "./KBRelationshipSection";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockCreateMutate = vi.fn();
const mockDeleteMutate = vi.fn();

vi.mock("@/lib/hooks/useKB", () => ({
  useKBEntries: () => ({
    data: {
      items: [
        { id: "entry-2", name: "Allies", entity_type: "faction" },
        { id: "entry-3", name: "The Forest", entity_type: "location" },
      ],
    },
  }),
  useCreateKBRelationship: () => ({
    mutate: mockCreateMutate,
    isPending: false,
  }),
  useDeleteKBRelationship: () => ({
    mutate: mockDeleteMutate,
    isPending: false,
  }),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeEntry(overrides: Partial<KBEntry> = {}): KBEntry {
  return {
    id: "entry-1",
    novel_id: "novel-1",
    entity_type: "character",
    name: "Hero",
    slug: "hero",
    status: "canon",
    tags: [],
    metadata: {},
    body: "A brave hero.",
    template_version: null,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeRelationship(overrides: Partial<KBRelationship> = {}): KBRelationship {
  return {
    id: "rel-1",
    source_id: "entry-1",
    target_id: "entry-2",
    rel_type: "member_of",
    label: "Leader",
    direction: "directed",
    metadata: {},
    source_name: "Hero",
    target_name: "Allies",
    source_type: "character",
    target_type: "faction",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

const defaultEntry = makeEntry();

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("KBRelationshipSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // -------------------------------------------------------------------------
  // Rendering — relationships list
  // -------------------------------------------------------------------------

  it("renders relationships list", () => {
    const relationships = [
      makeRelationship({ id: "rel-1", target_name: "Allies", rel_type: "member_of" }),
      makeRelationship({ id: "rel-2", target_name: "The Forest", rel_type: "lives_in" }),
    ];

    render(
      <KBRelationshipSection
        novelId="novel-1"
        entry={defaultEntry}
        relationships={relationships}
      />,
    );

    // Relationship names and types should be visible
    expect(screen.getByText("Allies")).toBeInTheDocument();
    expect(screen.getByText("member_of")).toBeInTheDocument();
    expect(screen.getByText("The Forest")).toBeInTheDocument();
    expect(screen.getByText("lives_in")).toBeInTheDocument();
  });

  it("renders relationship label when present", () => {
    const relationships = [makeRelationship({ label: "Leader" })];

    render(
      <KBRelationshipSection
        novelId="novel-1"
        entry={defaultEntry}
        relationships={relationships}
      />,
    );

    expect(screen.getByText("(Leader)")).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Empty state
  // -------------------------------------------------------------------------

  it("shows no entries message when relationships is empty", () => {
    render(<KBRelationshipSection novelId="novel-1" entry={defaultEntry} relationships={[]} />);

    expect(screen.getByText("kb.noEntries")).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Add relationship button
  // -------------------------------------------------------------------------

  it("renders add relationship button", () => {
    render(<KBRelationshipSection novelId="novel-1" entry={defaultEntry} relationships={[]} />);

    expect(screen.getByText("kb.addRelationship")).toBeInTheDocument();
  });

  it("opens add relationship dialog on button click", async () => {
    const user = userEvent.setup();
    render(<KBRelationshipSection novelId="novel-1" entry={defaultEntry} relationships={[]} />);

    await user.click(screen.getByText("kb.addRelationship"));

    // Dialog should be visible — has title, target input, rel type input
    await waitFor(() => {
      // The dialog header shows the same text as the button
      const headings = screen.getAllByText("kb.addRelationship");
      expect(headings.length).toBeGreaterThanOrEqual(2); // button + dialog title
    });

    // Dialog form elements should be visible
    expect(screen.getByLabelText("kb.targetEntry")).toBeInTheDocument();
    expect(screen.getByLabelText("kb.relType")).toBeInTheDocument();
  });

  it("dialog has cancel button that closes it", async () => {
    const user = userEvent.setup();
    render(<KBRelationshipSection novelId="novel-1" entry={defaultEntry} relationships={[]} />);

    // Open dialog
    await user.click(screen.getByText("kb.addRelationship"));

    // Find cancel buttons (button + dialog both have cancel)
    const cancelButtons = screen.getAllByText("kb.cancel");
    // Click the dialog cancel button (last one)
    await user.click(cancelButtons[cancelButtons.length - 1]);

    // Dialog should close — target entry input gone
    await waitFor(() => {
      expect(screen.queryByLabelText("kb.targetEntry")).not.toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Delete relationship
  // -------------------------------------------------------------------------

  it("delete button triggers delete mutation", async () => {
    const user = userEvent.setup();
    const relationships = [makeRelationship({ id: "rel-to-delete" })];

    render(
      <KBRelationshipSection
        novelId="novel-1"
        entry={defaultEntry}
        relationships={relationships}
      />,
    );

    const deleteButton = screen.getByLabelText("Delete relationship");
    await user.click(deleteButton);

    expect(mockDeleteMutate).toHaveBeenCalledWith("rel-to-delete");
  });

  // -------------------------------------------------------------------------
  // Create relationship via dialog
  // -------------------------------------------------------------------------

  it("create button in dialog triggers create mutation", async () => {
    const user = userEvent.setup();
    // Make create succeed so dialog closes
    mockCreateMutate.mockImplementation((_data: unknown, opts: { onSuccess?: () => void }) => {
      opts?.onSuccess?.();
    });

    render(<KBRelationshipSection novelId="novel-1" entry={defaultEntry} relationships={[]} />);

    // Open dialog
    await user.click(screen.getByText("kb.addRelationship"));

    // Fill in target (type in search)
    const targetInput = screen.getByLabelText("kb.targetEntry");
    await user.type(targetInput, "All");

    // Wait for search results
    await waitFor(() => {
      expect(screen.getByText("Allies (faction)")).toBeInTheDocument();
    });

    // Select a target
    await user.click(screen.getByText("Allies (faction)"));

    // Fill in relationship type
    const relTypeInput = screen.getByLabelText("kb.relType");
    await user.type(relTypeInput, "member_of");

    // Click create
    await user.click(screen.getByText("kb.create"));

    expect(mockCreateMutate).toHaveBeenCalledTimes(1);
    const callArgs = mockCreateMutate.mock.calls[0][0];
    expect(callArgs.source_id).toBe("entry-1");
    expect(callArgs.target_id).toBe("entry-2");
    expect(callArgs.rel_type).toBe("member_of");
  });

  // -------------------------------------------------------------------------
  // Section header
  // -------------------------------------------------------------------------

  it("renders section header", () => {
    render(<KBRelationshipSection novelId="novel-1" entry={defaultEntry} relationships={[]} />);

    expect(screen.getByText("kb.relationships")).toBeInTheDocument();
  });
});
