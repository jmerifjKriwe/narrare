import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PreferenceProfile } from "@/components/studio/settings/PreferenceProfile";
import type { PreferenceProfile as PreferenceProfileType } from "@/types";

const mockProfile: PreferenceProfileType = {
  user_id: "user-1",
  project_id: "project-1",
  event_count: 25,
  confidence: 0.75,
  style: { tone: "dramatic", pacing: "fast" },
  content: { themes: "coming-of-age", perspective: "first-person" },
  constraints: ["avoid clichés", "no deus ex machina"],
  last_updated: "2026-05-21T00:00:00Z",
};

describe("PreferenceProfile", () => {
  it("renders event count and confidence", () => {
    render(<PreferenceProfile profile={mockProfile} />);
    expect(screen.getByText("learning.statusInteractions")).toBeDefined();
    expect(screen.getByText("learning.confidence")).toBeDefined();
  });

  it("renders style patterns section", () => {
    render(<PreferenceProfile profile={mockProfile} />);
    expect(screen.getByText("learning.stylePatterns")).toBeDefined();
    expect(screen.getByText("tone: dramatic")).toBeDefined();
    expect(screen.getByText("pacing: fast")).toBeDefined();
  });

  it("renders content patterns section", () => {
    render(<PreferenceProfile profile={mockProfile} />);
    expect(screen.getByText("learning.contentPatterns")).toBeDefined();
    expect(screen.getByText("themes: coming-of-age")).toBeDefined();
  });

  it("renders avoidance patterns section", () => {
    render(<PreferenceProfile profile={mockProfile} />);
    expect(screen.getByText("learning.avoidancePatterns")).toBeDefined();
    expect(screen.getByText("avoid clichés")).toBeDefined();
    expect(screen.getByText("no deus ex machina")).toBeDefined();
  });

  it("shows profileEmpty when all sections are empty", () => {
    const emptyProfile: PreferenceProfileType = {
      ...mockProfile,
      style: {},
      content: {},
      constraints: [],
    };
    render(<PreferenceProfile profile={emptyProfile} />);
    expect(screen.getByText("learning.profileEmpty")).toBeDefined();
  });

  it("hides empty sections", () => {
    const partialProfile: PreferenceProfileType = {
      ...mockProfile,
      content: {},
      constraints: [],
    };
    render(<PreferenceProfile profile={partialProfile} />);
    expect(screen.getByText("learning.stylePatterns")).toBeDefined();
    expect(screen.queryByText("learning.contentPatterns")).toBeNull();
    expect(screen.queryByText("learning.avoidancePatterns")).toBeNull();
  });

  it("displays green confidence badge for high confidence", () => {
    render(<PreferenceProfile profile={{ ...mockProfile, confidence: 0.85 }} />);
    const badge = screen.getByText("learning.confidence");
    expect(badge.classList.toString()).toContain("green");
  });
});
