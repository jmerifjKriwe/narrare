/**
 * KBDetailPanel tests — column 3 detail/edit panel router.
 *
 * Tests:
 * 1. Shows empty state when no entry selected and not creating
 * 2. Shows KBCreateForm when isCreating=true
 * 3. Shows KBEntryDetail when entry is provided
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { KBDetailPanel } from "@/components/studio/kb/KBDetailPanel";
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
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/components/studio/kb/KBCreateForm", () => ({
  KBCreateForm: ({ initialEntityType }: { initialEntityType?: string }) => (
    <div data-testid="kb-create-form">Create Form — {initialEntityType ?? "none"}</div>
  ),
}));

vi.mock("@/components/studio/kb/KBEntryDetail", () => ({
  KBEntryDetail: ({ entry }: { entry: KBEntry }) => (
    <div data-testid="kb-entry-detail">{entry.name}</div>
  ),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function createEntry(overrides: Partial<KBEntry> = {}): KBEntry {
  return {
    id: "entry-1",
    novel_id: "novel-1",
    entity_type: "character",
    name: "Anna Schmidt",
    slug: "anna-schmidt",
    status: "canon",
    tags: [],
    metadata: {},
    body: "",
    template_version: null,
    created_at: "2026-01-10T10:00:00Z",
    updated_at: "2026-01-10T10:00:00Z",
    ...overrides,
  };
}

const defaultRels: KBRelationship[] = [];

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("KBDetailPanel", () => {
  it("shows empty state when no entry selected and not creating", () => {
    renderWithProviders(
      <KBDetailPanel
        novelId="novel-1"
        entry={null}
        relationships={defaultRels}
        isCreating={false}
        onCreateCancel={vi.fn()}
        onCreated={vi.fn()}
        onDeleted={vi.fn()}
      />,
    );

    expect(screen.getByText("kb.selectEntry")).toBeDefined();
    expect(screen.getByText("kb.orCreate")).toBeDefined();
  });

  it("shows KBCreateForm when isCreating=true", () => {
    renderWithProviders(
      <KBDetailPanel
        novelId="novel-1"
        entry={null}
        relationships={defaultRels}
        isCreating
        initialEntityType="character"
        onCreateCancel={vi.fn()}
        onCreated={vi.fn()}
        onDeleted={vi.fn()}
      />,
    );

    expect(screen.getByTestId("kb-create-form")).toBeDefined();
    expect(screen.getByText(/Create Form — character/)).toBeDefined();
  });

  it("shows KBEntryDetail when entry is provided", () => {
    renderWithProviders(
      <KBDetailPanel
        novelId="novel-1"
        entry={createEntry()}
        relationships={defaultRels}
        isCreating={false}
        onCreateCancel={vi.fn()}
        onCreated={vi.fn()}
        onDeleted={vi.fn()}
      />,
    );

    expect(screen.getByTestId("kb-entry-detail")).toBeDefined();
    expect(screen.getByText("Anna Schmidt")).toBeDefined();
  });

  it("passes entry to KBEntryDetail", () => {
    renderWithProviders(
      <KBDetailPanel
        novelId="novel-1"
        entry={createEntry({ name: "Johann Weber" })}
        relationships={defaultRels}
        isCreating={false}
        onCreateCancel={vi.fn()}
        onCreated={vi.fn()}
        onDeleted={vi.fn()}
      />,
    );

    expect(screen.getByText("Johann Weber")).toBeDefined();
  });

  it("prioritizes create mode over entry display", () => {
    renderWithProviders(
      <KBDetailPanel
        novelId="novel-1"
        entry={createEntry()}
        relationships={defaultRels}
        isCreating
        onCreateCancel={vi.fn()}
        onCreated={vi.fn()}
        onDeleted={vi.fn()}
      />,
    );

    // Should show create form, not detail
    expect(screen.getByTestId("kb-create-form")).toBeDefined();
    expect(screen.queryByTestId("kb-entry-detail")).toBeNull();
  });
});
