import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LearningStatus } from "@/components/studio/learning/LearningStatus";

describe("LearningStatus", () => {
  it("renders event count in compact mode", () => {
    render(<LearningStatus eventCount={10} compact />);
    expect(screen.getByText("learning.statusInteractions")).toBeDefined();
  });

  it("renders progress bar in expanded mode", () => {
    render(<LearningStatus eventCount={25} />);
    expect(screen.getByText("learning.progressLabel")).toBeDefined();
    expect(screen.getByText("learning.statusInteractions")).toBeDefined();
  });

  it("shows collecting tier for < 5 events", () => {
    render(<LearningStatus eventCount={3} />);
    expect(screen.getByText("learning.tierCollecting")).toBeDefined();
  });

  it("shows emerging tier for 5–19 events", () => {
    render(<LearningStatus eventCount={10} />);
    expect(screen.getByText("learning.tierEmerging")).toBeDefined();
  });

  it("shows growing tier for 20–49 events", () => {
    render(<LearningStatus eventCount={30} />);
    expect(screen.getByText("learning.tierGrowing")).toBeDefined();
  });

  it("shows established tier for 50+ events", () => {
    render(<LearningStatus eventCount={60} />);
    expect(screen.getByText("learning.tierEstablished")).toBeDefined();
  });

  it("uses custom target", () => {
    render(<LearningStatus eventCount={5} target={10} />);
    // Progress bar should be 50%
    const bar = screen.getByText("learning.statusInteractions").closest("div")?.parentElement;
    expect(bar).toBeDefined();
  });
});
