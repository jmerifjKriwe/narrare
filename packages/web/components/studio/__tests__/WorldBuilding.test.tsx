/**
 * WorldBuilding tests — 3-column KB browser orchestrator.
 *
 * Tests:
 * 1. Renders KBCategorySidebar
 * 2. Renders KBEntryList
 * 3. Renders KBDetailPanel in default mode
 * 4. Renders KBAssistedCreationPanel in assisted mode
 * 5. Renders WorldbuildingAnalysisPanel in analysis mode
 * 6. Renders ConsistencyCheckPanel in consistency mode
 * 7. Renders KnowledgeGraphView in graph mode
 *
 * Note: WorldBuilding uses many sub-components with hooks, so we mock
 * everything at the component level to test the routing logic.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { WorldBuilding } from "@/components/studio/WorldBuilding";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const navigationMocks = vi.hoisted(() => ({
  pathname: "/novel/novel-1/worldbuilding",
  push: vi.fn(),
  replace: vi.fn(),
  searchParams: new URLSearchParams(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => navigationMocks.pathname,
  useRouter: () => ({ push: navigationMocks.push, replace: navigationMocks.replace }),
  useSearchParams: () => navigationMocks.searchParams,
}));

vi.mock("@/lib/hooks/useKB", () => ({
  useKBEntries: () => ({
    data: { items: [], total: 0 },
    isLoading: false,
  }),
  useKBEntry: () => ({ data: null }),
  useKBRelationships: () => ({ data: [] }),
}));

vi.mock("@/components/studio/kb/KBCategorySidebar", () => ({
  KBCategorySidebar: ({
    onAnalyze,
    onConsistencyCheck,
    onShowGraph,
  }: {
    onAnalyze?: () => void;
    onConsistencyCheck?: () => void;
    onShowGraph?: () => void;
  }) => (
    <div data-testid="kb-category-sidebar">
      <button type="button" onClick={onAnalyze} data-testid="btn-analyze">
        Analyze
      </button>
      <button type="button" onClick={onConsistencyCheck} data-testid="btn-consistency">
        Consistency
      </button>
      <button type="button" onClick={onShowGraph} data-testid="btn-graph">
        Graph
      </button>
    </div>
  ),
}));

vi.mock("@/components/studio/kb/KBEntryList", () => ({
  KBEntryList: ({ onCreateAssisted }: { onCreateAssisted: () => void }) => (
    <div data-testid="kb-entry-list">
      <button type="button" onClick={onCreateAssisted} data-testid="btn-assisted">
        Assisted
      </button>
    </div>
  ),
}));

vi.mock("@/components/studio/kb/KBDetailPanel", () => ({
  KBDetailPanel: () => <div data-testid="kb-detail-panel" />,
}));

vi.mock("@/components/studio/kb/KBAssistedCreationPanel", () => ({
  KBAssistedCreationPanel: () => <div data-testid="kb-assisted-panel" />,
}));

vi.mock("@/components/studio/kb/WorldbuildingAnalysisPanel", () => ({
  WorldbuildingAnalysisPanel: () => <div data-testid="analysis-panel" />,
}));

vi.mock("@/components/studio/kb/ConsistencyCheckPanel", () => ({
  ConsistencyCheckPanel: () => <div data-testid="consistency-panel" />,
}));

vi.mock("@/components/studio/kb/KnowledgeGraphView", () => ({
  KnowledgeGraphView: () => <div data-testid="knowledge-graph-view" />,
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("WorldBuilding", () => {
  beforeEach(() => {
    navigationMocks.push.mockClear();
    navigationMocks.replace.mockClear();
    navigationMocks.searchParams = new URLSearchParams();
  });

  it("renders KBCategorySidebar by default", () => {
    render(<WorldBuilding novelId="novel-1" />);

    expect(screen.getByTestId("kb-category-sidebar")).toBeDefined();
  });

  it("renders KBEntryList by default", () => {
    render(<WorldBuilding novelId="novel-1" />);

    expect(screen.getByTestId("kb-entry-list")).toBeDefined();
  });

  it("renders KBDetailPanel by default", () => {
    render(<WorldBuilding novelId="novel-1" />);

    expect(screen.getByTestId("kb-detail-panel")).toBeDefined();
  });

  it("switches to analysis mode when analyze button clicked", () => {
    render(<WorldBuilding novelId="novel-1" />);

    fireEvent.click(screen.getByTestId("btn-analyze"));

    expect(screen.getByTestId("analysis-panel")).toBeDefined();
    expect(screen.queryByTestId("kb-detail-panel")).toBeNull();
  });

  it("switches to consistency mode when consistency button clicked", () => {
    render(<WorldBuilding novelId="novel-1" />);

    fireEvent.click(screen.getByTestId("btn-consistency"));

    expect(screen.getByTestId("consistency-panel")).toBeDefined();
    expect(screen.queryByTestId("kb-detail-panel")).toBeNull();
  });

  it("switches to graph mode when graph button clicked", () => {
    render(<WorldBuilding novelId="novel-1" />);

    fireEvent.click(screen.getByTestId("btn-graph"));

    expect(screen.getByTestId("knowledge-graph-view")).toBeDefined();
    expect(screen.queryByTestId("kb-entry-list")).toBeNull();
  });

  it("switches to assisted creation when assisted button clicked", () => {
    render(<WorldBuilding novelId="novel-1" />);

    fireEvent.click(screen.getByTestId("btn-assisted"));

    expect(screen.getByTestId("kb-assisted-panel")).toBeDefined();
    expect(screen.queryByTestId("kb-detail-panel")).toBeNull();
  });

  it("initializes mode from URL state", () => {
    navigationMocks.searchParams = new URLSearchParams("mode=analysis");

    render(<WorldBuilding novelId="novel-1" />);

    expect(screen.getByTestId("analysis-panel")).toBeDefined();
  });

  it("pushes URL state when mode changes", () => {
    render(<WorldBuilding novelId="novel-1" />);

    fireEvent.click(screen.getByTestId("btn-analyze"));

    expect(navigationMocks.push).toHaveBeenCalledWith(
      "/novel/novel-1/worldbuilding?mode=analysis",
      {
        scroll: false,
      },
    );
  });
});
