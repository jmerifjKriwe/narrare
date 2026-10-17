/**
 * KBEntryList tests — Column 2 entry list with search.
 *
 * Tests:
 * 1. Renders New Entry and AI buttons
 * 2. Renders search input
 * 3. Renders entry cards when entries provided
 * 4. Shows empty state when no entries
 * 5. Shows loading state
 * 6. Calls onCreateNew when New Entry clicked
 * 7. Calls onCreateAssisted when AI button clicked
 * 8. Calls onSelectEntry when entry card clicked
 * 9. Highlights selected entry
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { KBEntryList } from "@/components/studio/kb/KBEntryList";
import type { KBEntityType, KBEntry } from "@/lib/api/kb";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Stable setQuery reference so the component's useEffect([..., setQuery]) does
// not re-run on every render and clobber the typed value. The real hook returns
// a useCallback-stable setQuery; the mock must match that contract.
const { setQuery } = vi.hoisted(() => ({ setQuery: vi.fn() }));

vi.mock("@/lib/hooks/useKB", () => ({
  useKBDebouncedSearch: () => ({
    setQuery,
    data: null,
    isLoading: false,
  }),
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
    tags: ["protagonist"],
    metadata: {},
    body: "",
    template_version: null,
    created_at: "2026-01-10T10:00:00Z",
    updated_at: "2026-05-20T14:00:00Z",
    ...overrides,
  };
}

const defaultEntries: KBEntry[] = [
  createEntry(),
  createEntry({ id: "entry-2", name: "Johann Weber", status: "draft" }),
];

const defaultProps = {
  novelId: "novel-1",
  entries: defaultEntries,
  isLoading: false,
  selectedEntryId: null as string | null,
  activeType: null as KBEntityType | null,
  onSelectEntry: vi.fn(),
  onCreateNew: vi.fn(),
  onCreateAssisted: vi.fn(),
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("KBEntryList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders New Entry button", () => {
    render(<KBEntryList {...defaultProps} />);

    expect(screen.getByText("kb.newEntry")).toBeDefined();
  });

  it("renders AI-assisted creation button", () => {
    render(<KBEntryList {...defaultProps} />);

    expect(screen.getByText("kb.newWithAI")).toBeDefined();
  });

  it("renders search input", () => {
    render(<KBEntryList {...defaultProps} />);

    expect(screen.getByPlaceholderText("kb.search")).toBeDefined();
  });

  it("renders entry cards when entries provided", () => {
    render(<KBEntryList {...defaultProps} />);

    expect(screen.getByText("Anna Schmidt")).toBeDefined();
    expect(screen.getByText("Johann Weber")).toBeDefined();
  });

  it("shows empty state when no entries", () => {
    render(<KBEntryList {...defaultProps} entries={[]} />);

    expect(screen.getByText("kb.noEntries")).toBeDefined();
  });

  it("shows guided empty-state hint and CTA when the entire KB is empty", () => {
    render(<KBEntryList {...defaultProps} entries={[]} activeType={null} />);

    expect(screen.getByText("kb.emptyStateHint")).toBeDefined();
    expect(screen.getByText("kb.emptyStateCta")).toBeDefined();
  });

  it("hides guided hint when a type filter is active", () => {
    render(<KBEntryList {...defaultProps} entries={[]} activeType="character" />);

    // Generic message still present
    expect(screen.getByText("kb.noEntries")).toBeDefined();
    // But no guided hint / CTA
    expect(screen.queryByText("kb.emptyStateHint")).toBeNull();
    expect(screen.queryByText("kb.emptyStateCta")).toBeNull();
  });

  it("calls onCreateNew when the empty-state CTA is clicked", () => {
    const onCreateNew = vi.fn();
    render(
      <KBEntryList {...defaultProps} entries={[]} activeType={null} onCreateNew={onCreateNew} />,
    );

    fireEvent.click(screen.getByText("kb.emptyStateCta"));
    expect(onCreateNew).toHaveBeenCalled();
  });

  it("shows loading state when isLoading=true", () => {
    render(<KBEntryList {...defaultProps} entries={[]} isLoading />);

    // Loading shows the search text in loading state
    const loadingElements = screen.getAllByText("kb.search");
    expect(loadingElements.length).toBeGreaterThanOrEqual(1);
  });

  it("calls onCreateNew when New Entry button clicked", () => {
    const onCreateNew = vi.fn();
    render(<KBEntryList {...defaultProps} onCreateNew={onCreateNew} />);

    fireEvent.click(screen.getByText("kb.newEntry"));
    expect(onCreateNew).toHaveBeenCalled();
  });

  it("calls onCreateAssisted when AI button clicked", () => {
    const onCreateAssisted = vi.fn();
    render(<KBEntryList {...defaultProps} onCreateAssisted={onCreateAssisted} />);

    fireEvent.click(screen.getByText("kb.newWithAI"));
    expect(onCreateAssisted).toHaveBeenCalled();
  });

  it("calls onSelectEntry when entry card clicked", () => {
    const onSelectEntry = vi.fn();
    render(<KBEntryList {...defaultProps} onSelectEntry={onSelectEntry} />);

    fireEvent.click(screen.getByText("Anna Schmidt"));
    expect(onSelectEntry).toHaveBeenCalledWith("entry-1");
  });

  it("renders entry status badge", () => {
    render(<KBEntryList {...defaultProps} />);

    expect(screen.getByText("kb.status.canon")).toBeDefined();
    expect(screen.getByText("kb.status.draft")).toBeDefined();
  });

  it("renders entry tags", () => {
    render(<KBEntryList {...defaultProps} />);

    // "protagonist" may appear multiple times if tag input also shows it
    const tagElements = screen.getAllByText("protagonist");
    expect(tagElements.length).toBeGreaterThanOrEqual(1);
  });

  it("renders legacy entry with null tags without crashing", () => {
    // F10 regression: rows created before the schema seam fix persist
    // tags as SQL null (the API returns "tags": null while the TS type
    // says string[]); the list must render the entry, not crash blank.
    const legacyEntry = createEntry({
      tags: null as unknown as string[],
    });
    render(<KBEntryList {...defaultProps} entries={[legacyEntry]} />);

    expect(screen.getByText("Anna Schmidt")).toBeDefined();
    // No tag preview may leak from a null value
    expect(screen.queryByText("protagonist")).toBeNull();
  });

  it("updates search input value on change", () => {
    render(<KBEntryList {...defaultProps} />);

    const searchInput = screen.getByPlaceholderText("kb.search");
    fireEvent.change(searchInput, { target: { value: "Anna" } });

    expect(searchInput).toHaveProperty("value", "Anna");
  });
});
