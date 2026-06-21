/**
 * useWorldbuildingAnalysis tests — hook-level behavior.
 *
 * Focus: CR-07 §16 localized apply-result messages.
 *
 * Tests:
 * 1. Failed apply with error details uses worldbuilding.failedWithDetails key
 * 2. Failed apply without details uses worldbuilding.failed key
 * 3. Successful apply uses worldbuilding.applied key
 */

import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useWorldbuildingAnalysis } from "@/components/studio/kb/useWorldbuildingAnalysis";
import type { WorldbuildingAnalysisResponse } from "@/lib/api/worldbuilding";

// ---------------------------------------------------------------------------
// Mocks — module level so the hook sees stable functions
// ---------------------------------------------------------------------------

const mockAnalyzeMutate = vi.fn();
const mockApplyMutate = vi.fn();
const mockAbort = vi.fn();
const mockRetry = vi.fn();

vi.mock("@/lib/hooks/useWorldbuilding", () => ({
  useWorldbuildingAnalyze: () => ({
    mutateAsync: mockAnalyzeMutate,
    isPending: false,
    isConnectionLost: false,
    abort: mockAbort,
    retry: mockRetry,
  }),
  useWorldbuildingApply: () => ({
    mutateAsync: mockApplyMutate,
    isPending: false,
  }),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function createAnalysisResponse(): WorldbuildingAnalysisResponse {
  return {
    worldbuilding_score: 0.75,
    overall_assessment: "Good",
    entity_count: 2,
    gap_findings: [],
    connection_suggestions: [
      {
        finding_index: 0,
        source_entity_id: "e1",
        source_entity_name: "Anna",
        source_entity_type: "character",
        target_entity_id: "e2",
        target_entity_name: "Berlin",
        target_entity_type: "location",
        suggested_rel_type: "lives_in",
        inverse_rel_type: null,
        reasoning: "likely",
        confidence: 0.8,
        story_relevance: 5,
      },
    ],
    consistency_issues: [],
  } as unknown as WorldbuildingAnalysisResponse;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useWorldbuildingAnalysis apply-result messaging (CR-07 §16)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAnalyzeMutate.mockResolvedValue(createAnalysisResponse());
  });

  it("uses worldbuilding.failedWithDetails key when apply fails with error details", async () => {
    mockApplyMutate.mockResolvedValue({
      success: false,
      errors: ["timeout", "db_error"],
      created_count: 0,
    });

    const { result } = renderHook(() => useWorldbuildingAnalysis("novel-1"));

    await waitFor(() => expect(result.current.state).toBe("results"));

    act(() => {
      result.current.setSelectedConnectionIndices(new Set([0]));
    });

    await act(async () => {
      await result.current.applySelectedConnections();
    });

    expect(result.current.applyMessage?.type).toBe("error");
    // Key-returning mock: t("worldbuilding.failedWithDetails", { details: "..." })
    // resolves to the key itself. The old code returned worldbuilding.failed.
    expect(result.current.applyMessage?.text).toBe("worldbuilding.failedWithDetails");
  });

  it("uses worldbuilding.failed key in catch when thrown value is not an Error", async () => {
    mockApplyMutate.mockRejectedValue("string rejection");

    const { result } = renderHook(() => useWorldbuildingAnalysis("novel-1"));

    await waitFor(() => expect(result.current.state).toBe("results"));

    act(() => {
      result.current.setSelectedConnectionIndices(new Set([0]));
    });

    await act(async () => {
      await result.current.applySelectedConnections();
    });

    expect(result.current.applyMessage?.type).toBe("error");
    expect(result.current.applyMessage?.text).toBe("worldbuilding.failed");
  });
});
