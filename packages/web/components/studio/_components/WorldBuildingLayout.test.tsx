import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { KBEntry } from "@/lib/api/kb";
import { WorldBuildingLayout } from "./WorldBuildingLayout";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

vi.mock("@/lib/hooks/useKB", () => ({
  useKBEntries: () => ({ data: { total: 0, items: [] } }),
  useKBDebouncedSearch: () => ({
    setQuery: vi.fn(),
    data: null,
    isLoading: false,
  }),
}));

vi.mock("@/lib/hooks/useWiki", () => ({
  useWikiIndex: () => ({ data: undefined }),
}));

const entries: KBEntry[] = [
  {
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
    updated_at: "2026-05-20T14:00:00Z",
  },
];

describe("WorldBuildingLayout responsive baseline", () => {
  it("uses desktop columns and mobile progressive disclosure containers", () => {
    render(
      <WorldBuildingLayout
        novelId="novel-1"
        activeType={null}
        entries={entries}
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
    expect(screen.getByText("kb.title")).toBeInTheDocument();
    expect(screen.getByText("Anna Schmidt")).toBeInTheDocument();
    expect(screen.getByTestId("kb-detail")).toBeInTheDocument();

    const categorySidebar = layout.children[0]?.firstElementChild as HTMLElement | null;
    expect(categorySidebar).not.toBeNull();
    expect(categorySidebar).toHaveClass("w-full");
    expect(categorySidebar).toHaveClass("lg:w-56");
    expect(categorySidebar?.className.split(/\s+/)).not.toContain("w-56");

    const entryList = layout.children[1]?.firstElementChild as HTMLElement | null;
    expect(entryList).not.toBeNull();
    expect(entryList).toHaveClass("w-full");
    expect(entryList).toHaveClass("lg:w-64");
    expect(entryList?.className.split(/\s+/)).not.toContain("w-64");
  });
});
