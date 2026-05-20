import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { StoryboardScrollArrows } from "@/components/studio/planning/StoryboardScrollArrows";

/**
 * Unit tests for StoryboardScrollArrows component.
 *
 * The component reads scrollLeft/clientWidth/scrollWidth from a ref'd
 * container element. We create a mock element with configurable values
 * to test the different visibility states.
 *
 * ResizeObserver is polyfilled for jsdom.
 */

// Polyfill ResizeObserver for jsdom
class MockResizeObserver {
  constructor(_callback: ResizeObserverCallback) {}
  observe() {}
  unobserve() {}
  disconnect() {}
}
vi.stubGlobal("ResizeObserver", MockResizeObserver);

function createMockRef(overrides: Partial<HTMLDivElement> = {}) {
  const el = {
    scrollLeft: 0,
    clientWidth: 500,
    scrollWidth: 1000,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    scrollBy: vi.fn(),
    align: "" as const,
    ...overrides,
  } as unknown as HTMLDivElement;

  return { current: el, mockElement: el };
}

describe("StoryboardScrollArrows", () => {
  it("renders both arrows when overflow detected", async () => {
    const ref = createMockRef();
    await act(async () => {
      render(<StoryboardScrollArrows scrollContainerRef={ref} />);
    });

    // After useEffect runs, scrollWidth(1000) > clientWidth(500) → canScrollRight
    // scrollLeft(0) → not canScrollLeft
    expect(screen.queryByLabelText("Scroll left")).toBeNull();
    expect(screen.queryByLabelText("Scroll right")).not.toBeNull();
  });

  it("hides left arrow when scrolled to start", async () => {
    const ref = createMockRef({
      scrollLeft: 0,
      clientWidth: 500,
      scrollWidth: 1000,
    });
    await act(async () => {
      render(<StoryboardScrollArrows scrollContainerRef={ref} />);
    });
    expect(screen.queryByLabelText("Scroll left")).toBeNull();
  });

  it("shows left arrow when scrolled past start", async () => {
    const ref = createMockRef({
      scrollLeft: 100,
      clientWidth: 500,
      scrollWidth: 1000,
    });
    await act(async () => {
      render(<StoryboardScrollArrows scrollContainerRef={ref} />);
    });

    expect(screen.queryByLabelText("Scroll left")).not.toBeNull();
  });

  it("hides right arrow when scrolled to end", async () => {
    const ref = createMockRef({
      scrollLeft: 500,
      clientWidth: 500,
      scrollWidth: 1000,
    });
    await act(async () => {
      render(<StoryboardScrollArrows scrollContainerRef={ref} />);
    });

    expect(screen.queryByLabelText("Scroll right")).toBeNull();
  });

  it("calls scrollBy on right arrow click", async () => {
    const ref = createMockRef({
      scrollLeft: 0,
      clientWidth: 500,
      scrollWidth: 1000,
    });
    await act(async () => {
      render(<StoryboardScrollArrows scrollContainerRef={ref} />);
    });

    const rightButton = screen.getByLabelText("Scroll right");
    fireEvent.click(rightButton);
    expect(ref.mockElement.scrollBy).toHaveBeenCalledWith({
      left: 200,
      behavior: "smooth",
    });
  });

  it("calls scrollBy on left arrow click", async () => {
    const ref = createMockRef({
      scrollLeft: 100,
      clientWidth: 500,
      scrollWidth: 1000,
    });
    await act(async () => {
      render(<StoryboardScrollArrows scrollContainerRef={ref} />);
    });

    const leftButton = screen.getByLabelText("Scroll left");
    fireEvent.click(leftButton);
    expect(ref.mockElement.scrollBy).toHaveBeenCalledWith({
      left: -200,
      behavior: "smooth",
    });
  });

  it("does not render arrows when no scroll container ref", () => {
    const ref = { current: null };
    render(<StoryboardScrollArrows scrollContainerRef={ref} />);
    expect(screen.queryByLabelText("Scroll left")).toBeNull();
    expect(screen.queryByLabelText("Scroll right")).toBeNull();
  });

  it("registers scroll event listener and ResizeObserver", async () => {
    const ref = createMockRef();
    await act(async () => {
      render(<StoryboardScrollArrows scrollContainerRef={ref} />);
    });

    expect(ref.mockElement.addEventListener).toHaveBeenCalledWith("scroll", expect.any(Function), {
      passive: true,
    });
  });
});
