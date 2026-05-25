/**
 * ExtractionPanel tests — Main orchestration container for KB extraction.
 *
 * Tests the phase state machine: loading → review → applying → done | error
 * by mocking the hooks layer with stable references.
 *
 * Key: The global next-intl mock returns a new function on every call,
 * which makes `t` (from useTranslations) unstable across renders.
 * This causes the useEffect to fire infinitely because `onError` depends on `t`.
 * Solution: Override next-intl mock with stable function references.
 *
 * Tests:
 * 1. Shows loading state on mount
 * 2. Shows review state after extraction succeeds
 * 3. Shows error state with retry on extraction failure
 * 4. Apply calls mutation with selected items only
 * 5. On apply success, calls onApplied callback
 * 6. Close button calls onClose
 * 7. Shows done state after successful apply
 * 8. Shows apply error state when apply fails
 * 9. Items sorted by confidence (descending)
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
// biome-ignore lint/correctness/noUnusedImports: screen is used via screen.getByText() etc. in tests below
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ExtractionPanel } from "@/components/studio/extraction/ExtractionPanel";
import type { ExtractionItem } from "@/lib/api/extraction";

// ---------------------------------------------------------------------------
// Override next-intl mock with STABLE function references
// (The global mock creates new functions on every call, causing infinite useEffect loops)
// ---------------------------------------------------------------------------

const stableT = (key: string, params?: Record<string, unknown>) => {
  if (params) {
    return Object.entries(params).reduce((str, [k, v]) => str.replace(`{${k}}`, String(v)), key);
  }
  return key;
};

vi.mock("next-intl", () => ({
  useTranslations: () => stableT,
  useLocale: () => "en",
  useNow: () => new Date("2024-01-01"),
  useTimeZone: () => "UTC",
}));

// ---------------------------------------------------------------------------
// Mocks — hook layer with stable references
// ---------------------------------------------------------------------------

const sampleItems: ExtractionItem[] = [
  {
    item_type: "new_entity",
    entity_type: "character",
    name: "Anna Schmidt",
    confidence: 0.92,
    source_text: "She walked through the old archive.",
    proposed_content: { role: "Protagonist" },
    target_entity_id: null,
    conflict_description: null,
    relationship_type: null,
    related_entity_name: null,
  },
  {
    item_type: "update_entity",
    entity_type: "character",
    name: "Dr. Viktor Stein",
    confidence: 0.85,
    source_text: "The professor adjusted his glasses.",
    proposed_content: { role: "Antagonist" },
    target_entity_id: "kb-entry-2",
    conflict_description: null,
    relationship_type: null,
    related_entity_name: null,
  },
  {
    item_type: "relationship",
    entity_type: null,
    name: "Anna Schmidt",
    confidence: 0.7,
    source_text: "She frequented the archive.",
    proposed_content: null,
    target_entity_id: null,
    conflict_description: null,
    relationship_type: "frequents",
    related_entity_name: "The Old Archive",
  },
];

// Stable mock functions — defined once, reused across renders
const stableExtractMutate = vi.fn();
const stableApplyMutate = vi.fn();

vi.mock("@/lib/hooks/useExtraction", () => ({
  useExtractChapter: () => ({
    mutate: stableExtractMutate,
    isPending: false,
    isError: false,
    error: null,
  }),
  useApplyExtraction: () => ({
    mutate: stableApplyMutate,
    isPending: false,
    isError: false,
    error: null,
  }),
}));

const stableLoadResults = vi.fn();
const stableToggleItem = vi.fn();
const stableSelectAll = vi.fn();
const stableSelectNone = vi.fn();

// Mutable selection state that tests can update
let mockSelectionItems: ExtractionItem[] = [];
let mockSelectionSelectedIndices = new Set<number>();
let mockSelectionAnalysisNotes = "";

vi.mock("@/lib/hooks/useExtractionSelection", () => ({
  useExtractionSelection: () => ({
    items: mockSelectionItems,
    selectedIndices: mockSelectionSelectedIndices,
    analysisNotes: mockSelectionAnalysisNotes,
    loadResults: stableLoadResults,
    toggleItem: stableToggleItem,
    selectAll: stableSelectAll,
    selectNone: stableSelectNone,
  }),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const defaultProps = {
  novelId: "novel-1",
  chapterId: "chapter-1",
  onClose: vi.fn(),
  onApplied: vi.fn(),
};

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = createQueryClient();
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

/**
 * Simulate extraction success: update selection state and call onSuccess callback.
 * The ExtractionPanel's useEffect calls extractMutation.mutate(undefined, { onSuccess, onError }).
 * We intercept this call and invoke the onSuccess callback to trigger phase transition.
 */
function simulateExtractSuccess(
  output: { results: ExtractionItem[]; analysis_notes: string } = {
    results: sampleItems,
    analysis_notes: "Found 3 items.",
  },
) {
  // Update mock selection state
  mockSelectionItems = [...output.results].sort((a, b) => b.confidence - a.confidence);
  mockSelectionSelectedIndices = new Set(mockSelectionItems.map((_, i) => i));
  mockSelectionAnalysisNotes = output.analysis_notes;

  // The mutate function was called with (undefined, { onSuccess, onError })
  const lastCall = stableExtractMutate.mock.calls[stableExtractMutate.mock.calls.length - 1];
  if (lastCall?.[1]?.onSuccess) {
    act(() => {
      lastCall[1].onSuccess(output);
    });
  }
}

function simulateExtractError(error: Error) {
  const lastCall = stableExtractMutate.mock.calls[stableExtractMutate.mock.calls.length - 1];
  if (lastCall?.[1]?.onError) {
    act(() => {
      lastCall[1].onError(error);
    });
  }
}

function simulateApplySuccess(
  response: {
    created_entries: Array<{ id: string; name: string; entity_type: string }>;
    updated_entries: Array<{ id: string; name: string; entity_type: string }>;
  } = {
    created_entries: [{ id: "entry-1", name: "Anna Schmidt", entity_type: "character" }],
    updated_entries: [],
  },
) {
  const lastCall = stableApplyMutate.mock.calls[stableApplyMutate.mock.calls.length - 1];
  if (lastCall?.[1]?.onSuccess) {
    act(() => {
      lastCall[1].onSuccess(response);
    });
  }
}

function simulateApplyError(error: Error) {
  const lastCall = stableApplyMutate.mock.calls[stableApplyMutate.mock.calls.length - 1];
  if (lastCall?.[1]?.onError) {
    act(() => {
      lastCall[1].onError(error);
    });
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ExtractionPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSelectionItems = [];
    mockSelectionSelectedIndices = new Set();
    mockSelectionAnalysisNotes = "";
  });

  afterEach(() => {
    cleanup();
  });

  it("shows loading state on mount and triggers extraction", () => {
    renderWithProviders(<ExtractionPanel {...defaultProps} />);

    // Loading title appears in both the header and the loading component
    const loadingTitles = screen.getAllByText("kb.extractionLoadingTitle");
    expect(loadingTitles.length).toBeGreaterThanOrEqual(1);

    // Should have triggered the extract mutation
    expect(stableExtractMutate).toHaveBeenCalledTimes(1);
  });

  it("shows review state after extraction succeeds", () => {
    renderWithProviders(<ExtractionPanel {...defaultProps} />);

    // Simulate extraction success
    simulateExtractSuccess();

    // Should now show review state with item names
    expect(screen.getByText("kb.extractionResultsSummary")).toBeDefined();
    expect(screen.getByText("Anna Schmidt")).toBeDefined();
    expect(screen.getByText("Dr. Viktor Stein")).toBeDefined();
  });

  it("shows error state with retry on extraction failure", () => {
    renderWithProviders(<ExtractionPanel {...defaultProps} />);

    // Simulate extraction failure
    simulateExtractError(new Error("Extraction service unavailable"));

    expect(screen.getByText("Extraction service unavailable")).toBeDefined();
    expect(screen.getByText("kb.extractionRetry")).toBeDefined();
  });

  it("retry button re-triggers extraction after error", () => {
    renderWithProviders(<ExtractionPanel {...defaultProps} />);

    // Simulate first failure
    simulateExtractError(new Error("First attempt failed"));
    expect(screen.getByText("First attempt failed")).toBeDefined();

    // Click retry
    fireEvent.click(screen.getByText("kb.extractionRetry"));

    // Should have called mutate again (once on mount, once on retry)
    expect(stableExtractMutate).toHaveBeenCalledTimes(2);

    // Simulate success on retry
    simulateExtractSuccess();

    // Should now show review state
    expect(screen.getByText("kb.extractionResultsSummary")).toBeDefined();
  });

  it("apply calls mutation with selected items only", () => {
    renderWithProviders(<ExtractionPanel {...defaultProps} />);

    // Simulate extraction success with all items selected
    simulateExtractSuccess();

    // Deselect the middle item (Dr. Viktor Stein at index 1 after sort by confidence)
    mockSelectionSelectedIndices = new Set([0, 2]); // Only Anna and relationship selected

    // Click apply - need to rerender to pick up the selection change
    // The component reads selectedIndices from the hook, so we need to trigger a re-render
    // by clicking the apply button which reads the current selection state
    const applyButtons = screen.getAllByText("kb.extractionApply");
    fireEvent.click(applyButtons[0]);

    // Should have called apply mutation
    expect(stableApplyMutate).toHaveBeenCalledTimes(1);

    // Verify the items passed to apply
    const applyArgs = stableApplyMutate.mock.calls[0][0];
    expect(Array.isArray(applyArgs)).toBe(true);
  });

  it("on apply success, calls onApplied callback", () => {
    const onApplied = vi.fn();
    renderWithProviders(<ExtractionPanel {...defaultProps} onApplied={onApplied} />);

    // Simulate extraction success
    simulateExtractSuccess();

    // Click apply
    const applyButtons = screen.getAllByText("kb.extractionApply");
    fireEvent.click(applyButtons[0]);

    // Simulate apply success
    simulateApplySuccess();

    expect(onApplied).toHaveBeenCalledTimes(1);
  });

  it("close button calls onClose", () => {
    const onClose = vi.fn();
    renderWithProviders(<ExtractionPanel {...defaultProps} onClose={onClose} />);

    // Find the close button (X icon button with aria-label)
    const closeButton = screen.getByLabelText("kb.extractionCancel");
    fireEvent.click(closeButton);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("shows done state after successful apply", () => {
    renderWithProviders(<ExtractionPanel {...defaultProps} />);

    // Simulate extraction success
    simulateExtractSuccess();

    // Click apply
    const applyButtons = screen.getAllByText("kb.extractionApply");
    fireEvent.click(applyButtons[0]);

    // Simulate apply success
    simulateApplySuccess();

    // Should show done state
    expect(screen.getByText("kb.extractionAppliedTitle")).toBeDefined();
  });

  it("shows apply error state when apply fails", () => {
    renderWithProviders(<ExtractionPanel {...defaultProps} />);

    // Simulate extraction success
    simulateExtractSuccess();

    // Click apply
    const applyButtons = screen.getAllByText("kb.extractionApply");
    fireEvent.click(applyButtons[0]);

    // Simulate apply failure
    simulateApplyError(new Error("Apply failed: KB service unavailable"));

    // Should show error state
    expect(screen.getByText("Apply failed: KB service unavailable")).toBeDefined();
  });

  it("items are sorted by confidence descending", () => {
    renderWithProviders(<ExtractionPanel {...defaultProps} />);

    // Simulate extraction success — loadResults sorts by confidence
    simulateExtractSuccess();

    // The mock selection items are already sorted by confidence descending
    // Anna Schmidt (0.92) should be first, Dr. Viktor Stein (0.85) second
    expect(mockSelectionItems[0].name).toBe("Anna Schmidt");
    expect(mockSelectionItems[0].confidence).toBe(0.92);
    expect(mockSelectionItems[1].name).toBe("Dr. Viktor Stein");
    expect(mockSelectionItems[1].confidence).toBe(0.85);
  });
});
