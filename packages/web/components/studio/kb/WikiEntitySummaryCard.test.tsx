import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { WikiSummaryResponse } from "@/lib/api/wiki";
import type { useWikiRefresh } from "@/lib/hooks/useWiki";
import { WikiEntitySummaryCard } from "./WikiEntitySummaryCard";

// --- Fixtures (mirror the neighboring card tests' harness shape) ---

const baseSummary: WikiSummaryResponse = {
  id: "ws-1",
  novel_id: "novel-1",
  entity_id: "00000000-0000-0000-0000-000000000001",
  narrative_summary: "Keeps her mother's ring.",
  role_in_story: "Protagonist",
  key_attributes: ["resolute"],
  relationships: null,
  chapter_references: null,
  character_arc: null,
  status: "fresh",
  version: 1,
  generated_at: new Date("2026-10-15T00:00:00Z").toISOString(),
  refreshed_at: null,
};

const baseRefreshMutation = {
  mutate: vi.fn(),
  isPending: false,
} as unknown as ReturnType<typeof useWikiRefresh>;

describe("WikiEntitySummaryCard", () => {
  it("renders the entity NAME when the wire provides it (M11)", () => {
    render(
      <WikiEntitySummaryCard
        summary={{ ...baseSummary, entity_name: "Elara Thornwind" }}
        refreshMutation={baseRefreshMutation}
      />,
    );

    expect(screen.getByText("Elara Thornwind")).toBeDefined();
    expect(screen.queryByText(/^0000/)).toBeNull();
  });

  it("falls back to the entity id when the name is absent (M11)", () => {
    render(
      <WikiEntitySummaryCard
        summary={{ ...baseSummary, entity_name: null }}
        refreshMutation={baseRefreshMutation}
      />,
    );

    expect(screen.getByText(baseSummary.entity_id)).toBeDefined();
  });
});
