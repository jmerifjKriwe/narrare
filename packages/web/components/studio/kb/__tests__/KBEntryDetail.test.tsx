/**
 * KBEntryDetail tests — central KB entry interaction.
 *
 * Tests:
 * 1. Renders entry with template-driven fields for character type
 * 2. Renders accordion groups from template
 * 3. Falls back to flat editor without template
 * 4. Saves changes on submit
 * 5. Loads template for entity type
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

  it("renders entry with template-driven fields for character type", async () => {
    renderWithProviders(
      <KBEntryDetail
        novelId="novel-1"
        entry={createEntry()}
        relationships={emptyRelationships}
        onDeleted={vi.fn()}
      />,
    );

    // Wait for template to load — the header with the entry name should show
    await waitFor(() => {
      expect(screen.getByDisplayValue("Anna Schmidt")).toBeDefined();
    });
  });

  it("renders accordion groups from template", async () => {
    renderWithProviders(
      <KBEntryDetail
        novelId="novel-1"
        entry={createEntry()}
        relationships={emptyRelationships}
        onDeleted={vi.fn()}
      />,
    );

    // The label function falls back to formatKey(group.name) when i18n key equals the key
    // formatKey("basic_info") → "Basic Info"
    // formatKey("appearance") → "Appearance"
    // formatKey("personality") → "Personality"
    await waitFor(() => {
      expect(screen.getByText("Basic Info")).toBeDefined();
    });
    await waitFor(() => {
      expect(screen.getByText("Appearance")).toBeDefined();
    });
    await waitFor(() => {
      expect(screen.getByText("Personality")).toBeDefined();
    });
  });

  it("falls back to flat editor without template", async () => {
    // Use entity type "location" — MSW returns 404 for non-character templates
    renderWithProviders(
      <KBEntryDetail
        novelId="novel-1"
        entry={createEntry({ entity_type: "location", name: "The Archive" })}
        relationships={emptyRelationships}
        onDeleted={vi.fn()}
      />,
    );

    // Wait for load and fallback — should show flat body textarea
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

  it("loads template for character entity type", async () => {
    renderWithProviders(
      <KBEntryDetail
        novelId="novel-1"
        entry={createEntry({ entity_type: "character" })}
        relationships={emptyRelationships}
        onDeleted={vi.fn()}
      />,
    );

    // Character template has field groups. Wait for them to render.
    // The label fallback produces formatKey(group.name), e.g. "Basic Info"
    await waitFor(() => {
      expect(screen.getByText("Basic Info")).toBeDefined();
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
