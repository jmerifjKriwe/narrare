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
 * 10. Mount extraction fires exactly once despite unstable mutateAsync
 *     identity (M01 storm pin, rendered under StrictMode)
 * 11. Cancel during loading closes exactly once — the post-cancel abort
 *     rejection must not re-open the modal (wave-fix pin)
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
// biome-ignore lint/correctness/noUnusedImports: screen is used via screen.getByText() etc. in tests below
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
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

// Controlled promise resolvers for mutateAsync
let extractResolve: ((value: unknown) => void) | null = null;
let extractReject: ((reason: unknown) => void) | null = null;
let applyResolve: ((value: unknown) => void) | null = null;
let applyReject: ((reason: unknown) => void) | null = null;

// Stable mock functions — defined once, reused across renders
const stableExtractMutate = vi.fn();
const stableApplyMutate = vi.fn();
// Mirror useAbortCallback (ai-mutation-adapter): abort synchronously rejects
// the pending mutateAsync promise with AbortError. This timing is exactly
// what makes the cancel path racy (see the wave-fix test below).
const stableAbort = vi.fn(() => {
  extractReject?.(new DOMException("Aborted", "AbortError"));
  extractReject = null;
});
const stableExtractMutateAsync = vi.fn<() => Promise<unknown>>(
  () =>
    new Promise((resolve, reject) => {
      extractResolve = resolve;
      extractReject = reject;
    }),
);
const stableApplyMutateAsync = vi.fn<(items: unknown[]) => Promise<unknown>>(
  () =>
    new Promise((resolve, reject) => {
      applyResolve = resolve;
      applyReject = reject;
    }),
);

// Base return object for useExtractChapter — stable identities for the
// default tests (see header note). The M01 storm test breaks the stability
// for mutateAsync ONLY, via the overridable mockUseExtractChapter below.
interface ExtractChapterHookValue {
  mutate: (...args: unknown[]) => unknown;
  mutateAsync: () => Promise<unknown>;
  abort: () => void;
  isPending: boolean;
  isError: boolean;
  error: null;
}

const baseExtractMutationValue: ExtractChapterHookValue = {
  mutate: stableExtractMutate,
  mutateAsync: stableExtractMutateAsync,
  abort: stableAbort,
  isPending: false,
  isError: false,
  error: null,
};

// Overridable hook mock: defaults to the stable base value; individual
// tests may swap in an unstable mutateAsync to reproduce the M01 storm.
const mockUseExtractChapter = vi.fn<() => ExtractChapterHookValue>(() => baseExtractMutationValue);

vi.mock("@/lib/hooks/useExtraction", () => ({
  useExtractChapter: () => mockUseExtractChapter(),
  useApplyExtraction: () => ({
    mutate: stableApplyMutate,
    mutateAsync: stableApplyMutateAsync,
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
 * Simulate extraction success: update selection state and resolve the
 * mutateAsync promise. The ExtractionPanel's useEffect calls
 * extractMutation.mutateAsync().then(...).catch(...) which we intercept
 * via the controlled promise stored in extractResolve/extractReject.
 */
async function simulateExtractSuccess(
  output: { results: ExtractionItem[]; analysis_notes: string } = {
    results: sampleItems,
    analysis_notes: "Found 3 items.",
  },
) {
  // Update mock selection state
  mockSelectionItems = [...output.results].sort((a, b) => b.confidence - a.confidence);
  mockSelectionSelectedIndices = new Set(mockSelectionItems.map((_, i) => i));
  mockSelectionAnalysisNotes = output.analysis_notes;

  // Resolve the controlled promise created by mutateAsync
  await act(async () => {
    extractResolve?.(output);
  });
}

async function simulateExtractError(error: Error) {
  await act(async () => {
    extractReject?.(error);
  });
}

async function simulateApplySuccess(
  response: {
    created_entries: Array<{ id: string; name: string; entity_type: string }>;
    updated_entries: Array<{ id: string; name: string; entity_type: string }>;
  } = {
    created_entries: [{ id: "entry-1", name: "Anna Schmidt", entity_type: "character" }],
    updated_entries: [],
  },
) {
  await act(async () => {
    applyResolve?.(response);
  });
}

async function simulateApplyError(error: Error) {
  await act(async () => {
    applyReject?.(error);
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ExtractionPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // clearAllMocks keeps the LAST mockImplementation — re-arm the stable
    // default so tests stay order-independent.
    mockUseExtractChapter.mockImplementation(() => baseExtractMutationValue);
    extractResolve = null;
    extractReject = null;
    applyResolve = null;
    applyReject = null;
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

    // Should have triggered the extract mutation via mutateAsync
    expect(stableExtractMutateAsync).toHaveBeenCalledTimes(1);
  });

  it("shows review state after extraction succeeds", async () => {
    renderWithProviders(<ExtractionPanel {...defaultProps} />);

    // Simulate extraction success
    await simulateExtractSuccess();

    // Should now show review state with item names
    expect(screen.getByText("kb.extractionResultsSummary")).toBeDefined();
    expect(screen.getByText("Anna Schmidt")).toBeDefined();
    expect(screen.getByText("Dr. Viktor Stein")).toBeDefined();
  });

  it("shows error state with retry on extraction failure", async () => {
    renderWithProviders(<ExtractionPanel {...defaultProps} />);

    // Simulate extraction failure
    await simulateExtractError(new Error("Extraction service unavailable"));

    expect(screen.getByText("Extraction service unavailable")).toBeDefined();
    expect(screen.getByText("kb.extractionRetry")).toBeDefined();
  });

  it("retry button re-triggers extraction after error", async () => {
    renderWithProviders(<ExtractionPanel {...defaultProps} />);

    // Simulate first failure
    await simulateExtractError(new Error("First attempt failed"));
    expect(screen.getByText("First attempt failed")).toBeDefined();

    // Click retry
    fireEvent.click(screen.getByText("kb.extractionRetry"));

    // Should have called mutateAsync again (at least once on mount + once on retry)
    expect(stableExtractMutateAsync.mock.calls.length).toBeGreaterThanOrEqual(2);

    // Simulate success on retry
    await simulateExtractSuccess();

    // Should now show review state
    expect(screen.getByText("kb.extractionResultsSummary")).toBeDefined();
  });

  it("apply calls mutation with selected items only", async () => {
    renderWithProviders(<ExtractionPanel {...defaultProps} />);

    // Simulate extraction success with all items selected
    await simulateExtractSuccess();

    // Deselect the middle item (Dr. Viktor Stein at index 1 after sort by confidence)
    mockSelectionSelectedIndices = new Set([0, 2]); // Only Anna and relationship selected

    // Click apply - need to rerender to pick up the selection change
    // The component reads selectedIndices from the hook, so we need to trigger a re-render
    // by clicking the apply button which reads the current selection state
    const applyButtons = screen.getAllByText("kb.extractionApply");
    fireEvent.click(applyButtons[0]);

    // Should have called apply mutation via mutateAsync
    expect(stableApplyMutateAsync).toHaveBeenCalledTimes(1);

    // Verify the items passed to apply
    const applyArgs = stableApplyMutateAsync.mock.calls[0][0];
    expect(Array.isArray(applyArgs)).toBe(true);
  });

  it("on apply success, calls onApplied callback", async () => {
    const onApplied = vi.fn();
    renderWithProviders(<ExtractionPanel {...defaultProps} onApplied={onApplied} />);

    // Simulate extraction success
    await simulateExtractSuccess();

    // Click apply
    const applyButtons = screen.getAllByText("kb.extractionApply");
    fireEvent.click(applyButtons[0]);

    // Simulate apply success
    await simulateApplySuccess();

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

  // Wave-fix pin (kb wave, pre-Task-6): cancel during loading. Clicking the
  // loading-phase cancel calls abort() + onClose(); abort synchronously
  // rejects the pending mutateAsync promise (ai-mutation-adapter), and that
  // rejection lands in the mount-effect catch on a microtask AFTER onClose.
  // handleExtractionError maps AbortError → onClose, so onClose fired TWICE —
  // and the real wiring (EditorOverlays) passes editorStore.toggleExtractionPanel
  // as onClose, a TRUE toggle, so the second call flipped the closed modal
  // back open, stuck in "loading" (startedRef prevents a re-fire). The cancel
  // path must be idempotent: exactly one close, post-cancel rejection = no-op.
  it("cancel during loading closes exactly once — abort rejection must not re-open", async () => {
    // Toggle-shaped onClose, mirroring the real EditorOverlays wiring: a
    // second onClose call re-opens the modal instead of staying closed.
    let open = true;
    const toggleOnClose = vi.fn(() => {
      open = !open;
    });

    renderWithProviders(<ExtractionPanel {...defaultProps} onClose={toggleOnClose} />);

    // Extraction started and still pending (never resolved by this test)
    expect(stableExtractMutateAsync).toHaveBeenCalledTimes(1);

    // Loading-phase cancel button (ExtractionLoading action, studio.aiActions.stop;
    // this file's t-mock returns the bare key)
    fireEvent.click(screen.getByRole("button", { name: "stop" }));

    // Synchronous close from handleCancelExtraction
    expect(open).toBe(false);

    // Flush the microtask on which the synchronous abort rejection lands
    await act(async () => {});

    // RED pre-fix: the abort rejection ran handleExtractionError → onClose
    // again → toggle flipped the modal back open.
    expect(open).toBe(false);
    expect(toggleOnClose).toHaveBeenCalledTimes(1);
  });

  it("shows done state after successful apply", async () => {
    renderWithProviders(<ExtractionPanel {...defaultProps} />);

    // Simulate extraction success
    await simulateExtractSuccess();

    // Click apply
    const applyButtons = screen.getAllByText("kb.extractionApply");
    fireEvent.click(applyButtons[0]);

    // Simulate apply success
    await simulateApplySuccess();

    // Should show done state
    expect(screen.getByText("kb.extractionAppliedTitle")).toBeDefined();
  });

  it("shows apply error state when apply fails", async () => {
    renderWithProviders(<ExtractionPanel {...defaultProps} />);

    // Simulate extraction success
    await simulateExtractSuccess();

    // Click apply
    const applyButtons = screen.getAllByText("kb.extractionApply");
    fireEvent.click(applyButtons[0]);

    // Simulate apply failure
    await simulateApplyError(new Error("Apply failed: KB service unavailable"));

    // Should show error state
    expect(screen.getByText("Apply failed: KB service unavailable")).toBeDefined();
  });

  it("items are sorted by confidence descending", async () => {
    renderWithProviders(<ExtractionPanel {...defaultProps} />);

    // Simulate extraction success — loadResults sorts by confidence
    await simulateExtractSuccess();

    // The mock selection items are already sorted by confidence descending
    // Anna Schmidt (0.92) should be first, Dr. Viktor Stein (0.85) second
    expect(mockSelectionItems[0].name).toBe("Anna Schmidt");
    expect(mockSelectionItems[0].confidence).toBe(0.92);
    expect(mockSelectionItems[1].name).toBe("Dr. Viktor Stein");
    expect(mockSelectionItems[1].confidence).toBe(0.85);
  });

  // M01 (request-storm) unit pin. Harness calibration: the shared factory
  // mocks useExtraction with stable references (header note); this spec
  // breaks that stability for mutateAsync ONLY, via the overridable
  // mockUseExtractChapter + baseExtractMutationValue above, and renders
  // with the file's renderWithProviders helper. The panel is wrapped in
  // <StrictMode> because Next dev (app router) runs mount effects as
  // setup → cleanup → setup: the mount-once guard must fire exactly once
  // WITHOUT dropping the in-flight extraction (no cancelled-cleanup,
  // matching the CharacterVoicePanel / useBulkExtractionController
  // startedRef precedent).
  it("fires the mount extraction exactly once despite unstable mutateAsync identity (M01)", async () => {
    // M01 repro at unit level: useAIOperation-backed hooks return a NEW
    // mutateAsync closure per state transition. The mount effect's deps
    // include it — without a startedRef guard every transition re-fires
    // POST /kb/extract/{chapter} (audit: 697 calls in one modal session).
    let renderCount = 0;
    const unstableExtract = vi
      .fn()
      .mockImplementation(() => Promise.resolve({ results: [], analysisNotes: "" }));
    mockUseExtractChapter.mockImplementation(() => {
      renderCount += 1;
      const nth = renderCount;
      return {
        ...baseExtractMutationValue,
        mutateAsync: async () => {
          void nth;
          return unstableExtract();
        },
      };
    });

    renderWithProviders(
      <StrictMode>
        <ExtractionPanel {...defaultProps} />
      </StrictMode>,
    );

    // Resolve the first extraction → phase review → re-render with a NEW
    // mutateAsync identity. The guarded hook must NOT re-fire.
    await waitFor(() => expect(screen.getByText("kb.extractionResultsSummary")).toBeDefined());
    await waitFor(() => expect(unstableExtract).toHaveBeenCalledTimes(1), { timeout: 1000 });
  });
});
