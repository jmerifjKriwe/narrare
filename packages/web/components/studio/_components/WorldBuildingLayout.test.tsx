import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorldBuildingLayout } from "./WorldBuildingLayout";

vi.mock("../kb/KBCategorySidebar", () => ({
  KBCategorySidebar: () => <nav data-testid="kb-categories" />,
}));

vi.mock("../kb/KBEntryList", () => ({
  KBEntryList: () => <section data-testid="kb-entry-list" />,
}));

describe("WorldBuildingLayout responsive baseline", () => {
  it("uses desktop columns and mobile progressive disclosure containers", () => {
    render(
      <WorldBuildingLayout
        novelId="novel-1"
        activeType={null}
        entries={[]}
        entriesLoading={false}
        selectedEntryId={null}
        onSelectEntry={vi.fn()}
        onCreateNew={vi.fn()}
        onCreateAssisted={vi.fn()}
        onTypeChange={vi.fn()}
        onAnalyze={vi.fn()}
        onConsistencyCheck={vi.fn()}
        onShowGraph={vi.fn()}
        onShowWiki={vi.fn()}
        showGraph={false}
        showWiki={false}
      >
        <section data-testid="kb-detail" />
      </WorldBuildingLayout>,
    );

    const layout = screen.getByTestId("kb-responsive-layout");
    expect(layout.className).toContain("flex-col");
    expect(layout.className).toContain("lg:flex-row");
    expect(screen.getByTestId("kb-categories")).toBeInTheDocument();
    expect(screen.getByTestId("kb-entry-list")).toBeInTheDocument();
    expect(screen.getByTestId("kb-detail")).toBeInTheDocument();
  });
});
