/**
 * AddRelationshipDialog tests — dialog for creating KB relationships.
 *
 * AddRelationshipDialog is a non-exported component inside KBRelationshipSection,
 * so all tests drive through the parent component.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { KBRelationshipSection } from "@/components/studio/kb/KBRelationshipSection";
import type { KBEntry, KBRelationship } from "@/lib/api/kb";

// ---------------------------------------------------------------------------
// Mock hooks
// ---------------------------------------------------------------------------

const mockCreateMutate = vi.fn();
const mockDeleteMutate = vi.fn();

vi.mock("@/lib/hooks/useKB", () => ({
  useCreateKBRelationship: vi.fn(() => ({
    mutate: mockCreateMutate,
    isPending: false,
  })),
  useDeleteKBRelationship: vi.fn(() => ({
    mutate: mockDeleteMutate,
    isPending: false,
  })),
  useKBEntries: vi.fn(() => ({
    data: {
      items: [
        { id: "entry-2", name: "Alice", entity_type: "character" },
        { id: "entry-3", name: "Bob", entity_type: "character" },
        { id: "entry-4", name: "Castle", entity_type: "location" },
      ],
      total: 3,
      page: 1,
      page_size: 50,
    },
  })),
}));

// ---------------------------------------------------------------------------
// Test wrapper
// ---------------------------------------------------------------------------

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockEntry: KBEntry = {
  id: "entry-1",
  novel_id: "novel-1",
  entity_type: "character",
  name: "Test Entry",
  slug: "test-entry",
  status: "draft",
  tags: [],
  metadata: {},
  body: "",
  template_version: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const mockRelationships: KBRelationship[] = [
  {
    id: "rel-1",
    source_id: "entry-1",
    target_id: "entry-2",
    rel_type: "friend_of",
    label: "Best friends",
    direction: "mutual",
    metadata: {},
    source_name: "Test Entry",
    target_name: "Alice",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function openDialog() {
  const addButton = screen.getByRole("button", {
    name: /kb\.addRelationship/,
  });
  await userEvent.click(addButton);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AddRelationshipDialog (via KBRelationshipSection)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // --- Dialog open / close --------------------------------------------------

  it("opens dialog on Add Relationship button click", async () => {
    renderWithProviders(
      <KBRelationshipSection novelId="novel-1" entry={mockEntry} relationships={[]} />,
    );

    await openDialog();

    expect(screen.getByLabelText("kb.targetEntry")).toBeDefined();
  });

  it("closes dialog on Cancel button click", async () => {
    renderWithProviders(
      <KBRelationshipSection novelId="novel-1" entry={mockEntry} relationships={[]} />,
    );

    await openDialog();
    expect(screen.getByLabelText("kb.targetEntry")).toBeDefined();

    // getByText("kb.cancel") matches the Cancel text button (not the X icon)
    const cancelButton = screen.getByText("kb.cancel");
    await userEvent.click(cancelButton);

    await waitFor(() => {
      expect(screen.queryByLabelText("kb.targetEntry")).toBeNull();
    });
  });

  it("closes dialog on X button click", async () => {
    renderWithProviders(
      <KBRelationshipSection novelId="novel-1" entry={mockEntry} relationships={[]} />,
    );

    await openDialog();
    expect(screen.getByLabelText("kb.targetEntry")).toBeDefined();

    // getByLabelText("kb.cancel") matches the X icon button (has aria-label)
    const xButton = screen.getByLabelText("kb.cancel");
    await userEvent.click(xButton);

    await waitFor(() => {
      expect(screen.queryByLabelText("kb.targetEntry")).toBeNull();
    });
  });

  // --- Target autocomplete --------------------------------------------------

  it("shows filtered entries when typing in target search", async () => {
    renderWithProviders(
      <KBRelationshipSection novelId="novel-1" entry={mockEntry} relationships={[]} />,
    );

    await openDialog();

    const searchInput = screen.getByLabelText("kb.targetEntry");
    await userEvent.type(searchInput, "Ali");

    expect(screen.getByText(/Alice \(character\)/)).toBeDefined();
    expect(screen.queryByText(/Bob \(character\)/)).toBeNull();
    expect(screen.queryByText(/Castle \(location\)/)).toBeNull();
  });

  // --- Create button state --------------------------------------------------

  it("disables Create button when required fields are empty", async () => {
    renderWithProviders(
      <KBRelationshipSection novelId="novel-1" entry={mockEntry} relationships={[]} />,
    );

    await openDialog();

    const createButton = screen.getByRole("button", { name: "kb.create" });
    expect(createButton).toBeDisabled();
  });

  it("enables Create button when target and rel_type are filled", async () => {
    renderWithProviders(
      <KBRelationshipSection novelId="novel-1" entry={mockEntry} relationships={[]} />,
    );

    await openDialog();

    // Select target — type to filter, then click the entry
    const searchInput = screen.getByLabelText("kb.targetEntry");
    await userEvent.type(searchInput, "Ali");
    const aliceOption = screen.getByRole("button", {
      name: /Alice \(character\)/,
    });
    await userEvent.click(aliceOption);

    // Fill rel_type
    const relTypeInput = screen.getByLabelText("kb.relType");
    await userEvent.type(relTypeInput, "friend_of");

    const createButton = screen.getByRole("button", { name: "kb.create" });
    expect(createButton).not.toBeDisabled();
  });

  // --- Submit ---------------------------------------------------------------

  it("calls create mutation with correct data on submit", async () => {
    renderWithProviders(
      <KBRelationshipSection novelId="novel-1" entry={mockEntry} relationships={[]} />,
    );

    await openDialog();

    // Select target
    const searchInput = screen.getByLabelText("kb.targetEntry");
    await userEvent.type(searchInput, "Ali");
    const aliceOption = screen.getByRole("button", {
      name: /Alice \(character\)/,
    });
    await userEvent.click(aliceOption);

    // Fill rel_type
    const relTypeInput = screen.getByLabelText("kb.relType");
    await userEvent.type(relTypeInput, "friend_of");

    // Fill label
    const labelInput = screen.getByLabelText("kb.relLabel");
    await userEvent.type(labelInput, "Best friends");

    // Submit
    const createButton = screen.getByRole("button", { name: "kb.create" });
    await userEvent.click(createButton);

    expect(mockCreateMutate).toHaveBeenCalledWith(
      {
        source_id: "entry-1",
        target_id: "entry-2",
        rel_type: "friend_of",
        label: "Best friends",
        direction: "directed",
      },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
  });

  // --- Existing relationships -----------------------------------------------

  it("renders existing relationships with target name and rel type", () => {
    renderWithProviders(
      <KBRelationshipSection
        novelId="novel-1"
        entry={mockEntry}
        relationships={mockRelationships}
      />,
    );

    expect(screen.getByText("Alice")).toBeDefined();
    expect(screen.getByText("friend_of")).toBeDefined();
    expect(screen.getByText("(Best friends)")).toBeDefined();
  });

  it("calls delete mutation when delete button is clicked", async () => {
    renderWithProviders(
      <KBRelationshipSection
        novelId="novel-1"
        entry={mockEntry}
        relationships={mockRelationships}
      />,
    );

    const deleteButton = screen.getByLabelText("Delete relationship");
    await userEvent.click(deleteButton);

    expect(mockDeleteMutate).toHaveBeenCalledWith("rel-1");
  });

  it("shows empty message when no relationships exist", () => {
    renderWithProviders(
      <KBRelationshipSection novelId="novel-1" entry={mockEntry} relationships={[]} />,
    );

    expect(screen.getByText("kb.noEntries")).toBeDefined();
  });
});
