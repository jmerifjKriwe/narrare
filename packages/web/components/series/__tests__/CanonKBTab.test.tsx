/**
 * CanonKBTab component tests (Spec 1, Slice 5, Task 5.5).
 *
 * The Canon tab lists the Series-Canon KB entries (useCanonKB) and offers
 * create / edit / delete via the canon CRUD hooks. Each entry renders an entity
 * badge, its name, and a body preview; the "Create new Canon entry" button
 * opens an inline creation form.
 *
 * Conventions (mirrors BaendeList.test.tsx): the centralized setupTests.ts mock
 * returns i18n KEY STRINGS verbatim, so assertions check for keys. The canon
 * hooks (useCanonKB + CRUD mutations) are mocked per-file so each test controls
 * the resolved list and the mutation fns.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SeriesKBEntry } from "@/types";

// --- Per-file mutable mock state (hoisted) -----------------------------------
const mock = vi.hoisted(() => ({
  list: {
    data: undefined as SeriesKBEntry[] | undefined,
    isLoading: false,
    isError: false,
  },
  create: vi.fn(),
  createPending: false,
  update: vi.fn(),
  updatePending: false,
  remove: vi.fn(),
  removePending: false,
}));

vi.mock("@/lib/hooks/useCanonKB", () => ({
  useCanonKB: () => mock.list,
  useCreateCanonEntry: () => ({
    mutate: (...args: unknown[]) => mock.create(...args),
    isPending: mock.createPending,
  }),
  useUpdateCanonEntry: () => ({
    mutate: (...args: unknown[]) => mock.update(...args),
    isPending: mock.updatePending,
  }),
  useDeleteCanonEntry: () => ({
    mutate: (...args: unknown[]) => mock.remove(...args),
    isPending: mock.removePending,
  }),
}));

import { CanonKBTab } from "@/components/series/CanonKBTab";

// --- Fixtures ----------------------------------------------------------------
const canonEntries: SeriesKBEntry[] = [
  {
    id: "canon-1",
    entity_type: "character",
    name: "Holden",
    slug: "holden",
    status: "canon",
    body: "Captain of the Rocinante.",
    metadata_: null,
    tags: [],
    template_version: null,
    source: "manual",
    review_status: "reviewed",
    embeddings_dirty: false,
    last_referenced_at: null,
    usage_count: 0,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    scope: "series",
    series_id: "series-1",
    novel_id: null,
    base_entry_id: null,
  },
  {
    id: "canon-2",
    entity_type: "location",
    name: "Ceres Station",
    slug: "ceres-station",
    status: "canon",
    body: "Dwarf-planet beltway hub.",
    metadata_: null,
    tags: [],
    template_version: null,
    source: "manual",
    review_status: "reviewed",
    embeddings_dirty: false,
    last_referenced_at: null,
    usage_count: 0,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    scope: "series",
    series_id: "series-1",
    novel_id: null,
    base_entry_id: null,
  },
];

function resetState(): void {
  mock.list = { data: canonEntries, isLoading: false, isError: false };
  mock.create = vi.fn();
  mock.createPending = false;
  mock.update = vi.fn();
  mock.updatePending = false;
  mock.remove = vi.fn();
  mock.removePending = false;
}

describe("CanonKBTab", () => {
  beforeEach(() => {
    resetState();
  });

  it("shows a loading state while the canon list is loading", () => {
    mock.list = { data: undefined, isLoading: true, isError: false };
    render(<CanonKBTab seriesId="series-1" />);
    expect(screen.getByTestId("canon-kb-loading")).toBeDefined();
  });

  it("shows an error state when the canon list fails to load", () => {
    mock.list = { data: undefined, isLoading: false, isError: true };
    render(<CanonKBTab seriesId="series-1" />);
    expect(screen.getByTestId("canon-kb-error")).toBeDefined();
  });

  it("renders one row per canon entry with name and body preview", () => {
    render(<CanonKBTab seriesId="series-1" />);
    expect(screen.getAllByTestId("canon-entry-row")).toHaveLength(2);
    expect(screen.getByText("Holden")).toBeDefined();
    expect(screen.getByText("Captain of the Rocinante.")).toBeDefined();
  });

  it("renders an entity-type badge for each entry", () => {
    render(<CanonKBTab seriesId="series-1" />);
    expect(screen.getAllByTestId("canon-entry-badge")).toHaveLength(2);
  });

  it("shows an empty state when the series has no canon entries", () => {
    mock.list = { data: [], isLoading: false, isError: false };
    render(<CanonKBTab seriesId="series-1" />);
    expect(screen.getByTestId("canon-kb-empty")).toBeDefined();
  });

  it("renders the create-new-canon-entry button", () => {
    render(<CanonKBTab seriesId="series-1" />);
    expect(screen.getByTestId("canon-kb-create")).toBeDefined();
  });

  it("opens the inline creation form when the create button is clicked", async () => {
    const user = userEvent.setup();
    render(<CanonKBTab seriesId="series-1" />);

    expect(screen.queryByTestId("canon-kb-create-form")).toBeNull();
    await user.click(screen.getByTestId("canon-kb-create"));
    expect(screen.getByTestId("canon-kb-create-form")).toBeDefined();
  });

  it("creates a canon entry with name + entity type when the form is submitted", async () => {
    const user = userEvent.setup();
    render(<CanonKBTab seriesId="series-1" />);

    await user.click(screen.getByTestId("canon-kb-create"));
    const nameInput = screen.getByTestId("canon-kb-create-name") as HTMLInputElement;
    await user.type(nameInput, "Miller");
    await user.click(screen.getByTestId("canon-kb-create-submit"));

    await waitFor(() => {
      expect(mock.create).toHaveBeenCalledTimes(1);
    });
    const payload = mock.create.mock.calls[0][0];
    expect(payload).toMatchObject({ name: "Miller" });
    expect(payload.entity_type).toBeDefined();
  });

  it("expands an entry into edit mode when its row is clicked", async () => {
    const user = userEvent.setup();
    render(<CanonKBTab seriesId="series-1" />);

    expect(screen.queryByTestId("canon-entry-edit")).toBeNull();
    await user.click(screen.getAllByTestId("canon-entry-toggle")[0]);
    expect(screen.getByTestId("canon-entry-edit")).toBeDefined();
  });

  it("deletes an entry from edit mode when the delete button is confirmed", async () => {
    const user = userEvent.setup();
    render(<CanonKBTab seriesId="series-1" />);

    await user.click(screen.getAllByTestId("canon-entry-toggle")[0]);
    await user.click(screen.getByTestId("canon-entry-delete"));
    // Destructive → confirmation gate.
    await user.click(screen.getByTestId("confirm-dialog-confirm"));

    // I-F3: remove is called with the entry id + an onSuccess callback that
    // closes the confirm dialog only on success.
    expect(mock.remove).toHaveBeenCalledWith(
      "canon-1",
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
  });
});
