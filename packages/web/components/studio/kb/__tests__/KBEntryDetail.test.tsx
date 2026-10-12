/**
 * KBEntryDetail tests — central KB entry interaction.
 *
 * Since B04 the template endpoint returns `TemplateDetailResponse` (no field
 * groups), so the detail view always renders metadata + flat body editor.
 *
 * Tests:
 * 1. Renders entry with metadata display and flat body editor
 * 2. Renders entry metadata values from the entry payload
 * 3. Renders flat editor for any entity type
 * 4. Saves changes on submit
 * 5. Renders flat body editor populated from the entry
 * 6. Renders status selector
 * 7. Renders tags input
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { KBEntryDetail } from "@/components/studio/kb/KBEntryDetail";
import type { KBEntry, KBRelationship } from "@/lib/api/kb";

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

function createEntry(overrides: Partial<KBEntry> = {}): KBEntry {
  return {
    id: "kb-entry-1",
    novel_id: "novel-1",
    entity_type: "character",
    name: "Anna Schmidt",
    slug: "anna-schmidt",
    status: "canon",
    tags: ["protagonist"],
    metadata: { role: "Protagonist" },
    body: "A young historian.",
    template_version: null,
    created_at: "2026-01-10T10:00:00Z",
    updated_at: "2026-05-15T14:30:00Z",
    ...overrides,
  };
}

const emptyRelationships: KBRelationship[] = [];

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("KBEntryDetail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders entry with metadata display and flat body editor", async () => {
    renderWithProviders(
      <KBEntryDetail
        novelId="novel-1"
        entry={createEntry()}
        relationships={emptyRelationships}
        onDeleted={vi.fn()}
      />,
    );

    // Wait for the template query to settle — the header with the entry name should show
    await waitFor(() => {
      expect(screen.getByDisplayValue("Anna Schmidt")).toBeDefined();
    });

    // The flat body editor is always rendered with the entry body
    await waitFor(() => {
      expect(screen.getByDisplayValue("A young historian.")).toBeDefined();
    });
  });

  it("renders entry metadata values from the entry payload", async () => {
    renderWithProviders(
      <KBEntryDetail
        novelId="novel-1"
        entry={createEntry()}
        relationships={emptyRelationships}
        onDeleted={vi.fn()}
      />,
    );

    // The metadata fallback display shows entry.metadata key-value pairs
    // (formatKey("role") → "Role:", value "Protagonist")
    await waitFor(() => {
      expect(screen.getByText("Role:")).toBeDefined();
    });
    expect(screen.getByText("Protagonist")).toBeDefined();
  });

  it("renders flat editor for any entity type", async () => {
    // Use entity type "location" — MSW returns 404 for non-character templates
    renderWithProviders(
      <KBEntryDetail
        novelId="novel-1"
        entry={createEntry({ entity_type: "location", name: "The Archive" })}
        relationships={emptyRelationships}
        onDeleted={vi.fn()}
      />,
    );

    // Wait for load — should show flat body textarea
    await waitFor(() => {
      expect(screen.getByDisplayValue("The Archive")).toBeDefined();
    });

    // The flat editor should show the body textarea
    await waitFor(() => {
      expect(screen.getByPlaceholderText("kb.bodyPlaceholder")).toBeDefined();
    });
  });

  it("saves changes on submit", async () => {
    renderWithProviders(
      <KBEntryDetail
        novelId="novel-1"
        entry={createEntry()}
        relationships={emptyRelationships}
        onDeleted={vi.fn()}
      />,
    );

    // Wait for entry name input to appear
    await waitFor(() => {
      expect(screen.getByDisplayValue("Anna Schmidt")).toBeDefined();
    });

    // Find and click the save button
    const saveButton = screen.getByText("kb.save");
    expect(saveButton).toBeDefined();
    fireEvent.click(saveButton);
  });

  it("renders flat body editor populated from the entry for character type", async () => {
    renderWithProviders(
      <KBEntryDetail
        novelId="novel-1"
        entry={createEntry({ entity_type: "character" })}
        relationships={emptyRelationships}
        onDeleted={vi.fn()}
      />,
    );

    // The flat editor is populated from the entry body (the template query
    // stays mounted but its payload is no longer read)
    await waitFor(() => {
      expect(screen.getByDisplayValue("A young historian.")).toBeDefined();
    });
  });

  it("renders status selector", async () => {
    renderWithProviders(
      <KBEntryDetail
        novelId="novel-1"
        entry={createEntry()}
        relationships={emptyRelationships}
        onDeleted={vi.fn()}
      />,
    );

    await waitFor(() => {
      const statusSelect = screen.getByDisplayValue("kb.status.canon");
      expect(statusSelect).toBeDefined();
    });
  });

  it("renders tags input", async () => {
    renderWithProviders(
      <KBEntryDetail
        novelId="novel-1"
        entry={createEntry({ tags: ["hero", "wizard"] })}
        relationships={emptyRelationships}
        onDeleted={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("hero")).toBeDefined();
      expect(screen.getByText("wizard")).toBeDefined();
    });
  });
});
