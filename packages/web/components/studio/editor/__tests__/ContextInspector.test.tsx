import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ContextInspector } from "@/components/studio/editor/ContextInspector";
import type { ContextMeta } from "@/lib/api/generation";

describe("ContextInspector", () => {
  const sampleMeta: ContextMeta = {
    type: "context_meta",
    kb_characters_count: 3,
    kb_locations_count: 1,
    kb_factions_count: 0,
    kb_suggested_count: 2,
    kb_pinned_count: 0,
    recent_chapter_count: 2,
    character_names: ["Anna", "Johann", "Waldgeist"],
    location_names: ["Försterhaus"],
    faction_names: [],
    is_first_chapter: false,
    has_user_preferences: true,
    tone: "dramatic",
    total_budget_tokens: 8000,
  };

  it("renders nothing when meta is null", () => {
    const { container } = render(<ContextInspector meta={null} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders info icon with entity summary", () => {
    render(<ContextInspector meta={sampleMeta} />);
    expect(screen.getByText(/3.*contextInspector.characters/)).toBeDefined();
    expect(screen.getByText(/1.*contextInspector.locations/)).toBeDefined();
  });

  it("renders noContext when all counts are zero", () => {
    const emptyMeta: ContextMeta = {
      ...sampleMeta,
      kb_characters_count: 0,
      kb_locations_count: 0,
      kb_factions_count: 0,
      recent_chapter_count: 0,
    };
    render(<ContextInspector meta={emptyMeta} />);
    expect(screen.getByText("contextInspector.noContext")).toBeDefined();
  });

  it("expands detail panel on click", () => {
    render(<ContextInspector meta={sampleMeta} />);
    // Entity names should NOT be visible initially
    expect(screen.queryByText("Anna")).toBeNull();
    // Click toggle
    fireEvent.click(screen.getByRole("button"));
    // Now names should be visible
    expect(screen.getByText("Anna")).toBeDefined();
    expect(screen.getByText("Johann")).toBeDefined();
  });

  it("shows tone in expanded panel", () => {
    render(<ContextInspector meta={sampleMeta} />);
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText(/dramatic/)).toBeDefined();
  });

  it("shows preferences active badge when present", () => {
    render(<ContextInspector meta={sampleMeta} />);
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("contextInspector.preferencesActive")).toBeDefined();
  });
});
