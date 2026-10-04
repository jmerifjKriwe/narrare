/**
 * ResolutionSuggestionsList tests — minimal ADR-085 suggestions review
 * (F3 plan Task 5, spec §8).
 *
 * The real component runs against the REAL "en" studio catalog (per-file
 * real-catalog pattern) with only the transport boundary mocked
 * (`@/lib/api/kbResolution`). Covered:
 *
 * 1. loading / error(+retry) / empty states,
 * 2. pairs render with names, confidence and band,
 * 3. endorse removes the row optimistically (endpoint called with the
 *    stateless suggestion id),
 * 4. endorse failure rolls the row back and surfaces an alert,
 * 5. a 409 stale endorse gets its own copy (expected concurrent resolve),
 * 6. reject (204 path) removes the row,
 * 7. NO automatic refetch after an action — the endorse endpoint invalidates
 *    the server analysis cache, so a refetch would serve the EMPTY
 *    miss-response and wipe still-unreviewed pairs (the explicit Re-check
 *    on the dedup card is the authoritative refresh).
 *
 * @module ResolutionSuggestionsList.test
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ResolutionSuggestionsList } from "./ResolutionSuggestionsList";

// ---------------------------------------------------------------------------
// next-intl — REAL "en" studio catalog (real-catalog pattern)
// ---------------------------------------------------------------------------

vi.mock("next-intl", async () => {
  const actual = await vi.importActual<typeof import("next-intl")>("next-intl");
  const studio = (await import("../../../../i18n/messages/en/studio.json")).default;
  return {
    ...actual,
    useTranslations: () =>
      actual.createTranslator({ locale: "en", messages: { studio }, namespace: "studio" }),
  };
});

// ---------------------------------------------------------------------------
// Transport mock
// ---------------------------------------------------------------------------

const handle = vi.hoisted(() => ({
  list: vi.fn(),
  analyze: vi.fn(),
  endorse: vi.fn(),
  reject: vi.fn(),
}));

vi.mock("@/lib/api/kbResolution", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/kbResolution")>();
  return {
    ...actual,
    kbResolutionApi: {
      listSuggestions: handle.list,
      analyzeSuggestions: handle.analyze,
      endorseSuggestion: handle.endorse,
      rejectSuggestion: handle.reject,
    },
  };
});

import { type ResolutionAnalysisResponse, ResolutionApiError } from "@/lib/api/kbResolution";

const NOVEL = "novel-1";

function suggestion(overrides: Partial<ResolutionAnalysisResponse["suggestions"][number]> = {}) {
  return {
    suggestion_id: "sug-aaa",
    entry_a_id: "10000000-0000-0000-0000-000000000001",
    entry_b_id: "20000000-0000-0000-0000-000000000002",
    name_a: "Elena Varo",
    name_b: "Elena Maren",
    confidence: 0.82,
    band: "REVIEW" as const,
    auto_merge_eligible: false,
    signals: [],
    adjudication_note: null,
    ...overrides,
  };
}

function analysisResult(suggestions: ReturnType<typeof suggestion>[]): ResolutionAnalysisResponse {
  return {
    suggestions,
    stats: { review: suggestions.length, auto_eligible: 0, suppressed: 0 },
    cache_hit: false,
  };
}

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function renderList() {
  render(
    <QueryClientProvider client={createQueryClient()}>
      <ResolutionSuggestionsList novelId={NOVEL} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  handle.list.mockResolvedValue(analysisResult([]));
  handle.analyze.mockResolvedValue(analysisResult([]));
  handle.endorse.mockResolvedValue({
    survivor_id: "10000000-0000-0000-0000-000000000001",
    loser_id: "20000000-0000-0000-0000-000000000002",
    merged_fact_keys: [],
    repointed_relationships: 0,
    skipped_relationships: 0,
    conflicts: [],
  });
  handle.reject.mockResolvedValue(undefined);
});

afterEach(cleanup);

describe("ResolutionSuggestionsList — states", () => {
  it("renders a loading state while the suggestions fetch is pending", () => {
    handle.list.mockReturnValue(new Promise(() => {}));
    renderList();
    expect(screen.getByText("Loading duplicates…")).toBeInTheDocument();
  });

  it("renders the failure copy with a Retry button that refetches", async () => {
    handle.list.mockRejectedValueOnce(new ResolutionApiError(500, "HTTP 500"));
    renderList();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Could not load the duplicate suggestions.",
    );

    handle.list.mockResolvedValueOnce(analysisResult([]));
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(screen.getByText("No duplicates detected.")).toBeInTheDocument());
  });

  it("renders the empty state for an analysis without suggestions", async () => {
    renderList();
    expect(await screen.findByText("No duplicates detected.")).toBeInTheDocument();
  });
});

describe("ResolutionSuggestionsList — pairs and actions", () => {
  const PAIRS = analysisResult([
    suggestion(),
    suggestion({
      suggestion_id: "sug-bbb",
      name_a: "Marcus Weber",
      name_b: "M. Weber",
      confidence: 0.95,
      band: "AUTO_ELIGIBLE",
      auto_merge_eligible: true,
      adjudication_note: "Identical arc, abbreviated form.",
    }),
  ]);

  it("renders each pair with names, confidence, band and the adjudication note", async () => {
    handle.list.mockResolvedValue(PAIRS);
    renderList();

    expect(await screen.findByText("Elena Varo ↔ Elena Maren")).toBeInTheDocument();
    expect(screen.getByText("Marcus Weber ↔ M. Weber")).toBeInTheDocument();
    expect(screen.getByText(/82% match/)).toBeInTheDocument();
    expect(screen.getByText(/95% match/)).toBeInTheDocument();
    expect(screen.getByText(/Needs review/)).toBeInTheDocument();
    expect(screen.getByText(/High confidence/)).toBeInTheDocument();
    expect(screen.getByText("Identical arc, abbreviated form.")).toBeInTheDocument();

    // Every row carries the endorse/reject pair of buttons.
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    for (const row of rows) {
      expect(within(row).getByRole("button", { name: "Merge" })).toBeInTheDocument();
      expect(within(row).getByRole("button", { name: "Dismiss" })).toBeInTheDocument();
    }
  });

  it("endorse calls the endpoint with the suggestion id and removes the row optimistically", async () => {
    handle.list.mockResolvedValue(PAIRS);
    renderList();
    const row = await screen.findByText("Elena Varo ↔ Elena Maren");
    fireEvent.click(
      within(row.closest("li") as HTMLElement).getByRole("button", { name: "Merge" }),
    );

    await waitFor(() => expect(handle.endorse).toHaveBeenCalledWith(NOVEL, "sug-aaa"));
    await waitFor(() =>
      expect(screen.queryByText("Elena Varo ↔ Elena Maren")).not.toBeInTheDocument(),
    );
    // The OTHER pair survives the optimistic removal.
    expect(screen.getByText("Marcus Weber ↔ M. Weber")).toBeInTheDocument();
    // No automatic refetch (would serve the empty miss-response — see header).
    expect(handle.list).toHaveBeenCalledTimes(1);
  });

  it("rolls a failed endorse back: the row returns and an alert explains", async () => {
    handle.list.mockResolvedValue(PAIRS);
    handle.endorse.mockRejectedValueOnce(new ResolutionApiError(500, "HTTP 500"));
    renderList();
    const row = await screen.findByText("Elena Varo ↔ Elena Maren");
    fireEvent.click(
      within(row.closest("li") as HTMLElement).getByRole("button", { name: "Merge" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The action failed — the pair is back in the list.",
    );
    await waitFor(() => expect(screen.getByText("Elena Varo ↔ Elena Maren")).toBeInTheDocument());
  });

  it("a 409 stale endorse gets its own copy (the pair was resolved elsewhere)", async () => {
    handle.list.mockResolvedValue(PAIRS);
    handle.endorse.mockRejectedValueOnce(new ResolutionApiError(409, "Suggestion is stale"));
    renderList();
    const row = await screen.findByText("Elena Varo ↔ Elena Maren");
    fireEvent.click(
      within(row.closest("li") as HTMLElement).getByRole("button", { name: "Merge" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This pair was already resolved elsewhere.",
    );
  });

  it("reject calls the 204 endpoint and removes the row", async () => {
    handle.list.mockResolvedValue(PAIRS);
    renderList();
    const row = await screen.findByText("Marcus Weber ↔ M. Weber");
    fireEvent.click(
      within(row.closest("li") as HTMLElement).getByRole("button", { name: "Dismiss" }),
    );

    await waitFor(() => expect(handle.reject).toHaveBeenCalledWith(NOVEL, "sug-bbb"));
    await waitFor(() =>
      expect(screen.queryByText("Marcus Weber ↔ M. Weber")).not.toBeInTheDocument(),
    );
    expect(screen.getByText("Elena Varo ↔ Elena Maren")).toBeInTheDocument();
  });

  it("a failed reject rolls the row back", async () => {
    handle.list.mockResolvedValue(PAIRS);
    handle.reject.mockRejectedValueOnce(new ResolutionApiError(500, "HTTP 500"));
    renderList();
    const row = await screen.findByText("Marcus Weber ↔ M. Weber");
    fireEvent.click(
      within(row.closest("li") as HTMLElement).getByRole("button", { name: "Dismiss" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The action failed — the pair is back in the list.",
    );
    await waitFor(() => expect(screen.getByText("Marcus Weber ↔ M. Weber")).toBeInTheDocument());
  });
});
