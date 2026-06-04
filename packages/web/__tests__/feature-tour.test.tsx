/**
 * FeatureTour component tests.
 *
 * Tests:
 * 1. Renders when localStorage key is absent
 * 2. Does not render when localStorage key is "true"
 * 3. Advances step on Next click
 * 4. Goes back on Back click
 * 5. Completes tour and sets localStorage on Skip
 * 6. Completes tour on Done (last step Next)
 * 7. Shows step indicator dots matching step count
 * 8. Keyboard Escape skips tour
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it } from "vitest";
import { FeatureTour, TOUR_STORAGE_KEY, type TourStep } from "@/components/ui/feature-tour";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockSteps: TourStep[] = [
  {
    target: "main",
    titleKey: "tour.step1.title",
    descriptionKey: "tour.step1.description",
  },
  {
    titleKey: "tour.step2.title",
    descriptionKey: "tour.step2.description",
  },
  {
    target: "a[href*='settings']",
    titleKey: "tour.step3.title",
    descriptionKey: "tour.step3.description",
  },
];

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  cleanup();
});

function renderTour(steps: TourStep[] = mockSteps) {
  return render(<FeatureTour steps={steps} />);
}

it("renders when localStorage key is absent", () => {
  renderTour();
  expect(screen.getByRole("dialog")).toBeInTheDocument();
});

it("does not render when localStorage key is 'true'", () => {
  localStorage.setItem(TOUR_STORAGE_KEY, "true");
  renderTour();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("does not render when steps array is empty", () => {
  renderTour([]);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("shows step indicator dots matching step count", () => {
  renderTour();
  // next-intl mock returns key strings, find the tour.skip text
  const dialog = screen.getByRole("dialog");
  const dots = dialog.querySelectorAll(".rounded-full");
  expect(dots).toHaveLength(mockSteps.length);
});

it("displays first step title and description", () => {
  renderTour();
  expect(screen.getByText("tour.step1.title")).toBeInTheDocument();
  expect(screen.getByText("tour.step1.description")).toBeInTheDocument();
});

it("advances to next step on Next click", () => {
  renderTour();
  const nextBtn = screen.getByText("tour.next");
  fireEvent.click(nextBtn);
  expect(screen.getByText("tour.step2.title")).toBeInTheDocument();
  expect(screen.queryByText("tour.step1.title")).not.toBeInTheDocument();
});

it("does not show Back button on first step", () => {
  renderTour();
  expect(screen.queryByText("tour.back")).not.toBeInTheDocument();
});

it("shows Back button after advancing", () => {
  renderTour();
  fireEvent.click(screen.getByText("tour.next"));
  expect(screen.getByText("tour.back")).toBeInTheDocument();
});

it("goes back on Back click", () => {
  renderTour();
  fireEvent.click(screen.getByText("tour.next"));
  fireEvent.click(screen.getByText("tour.back"));
  expect(screen.getByText("tour.step1.title")).toBeInTheDocument();
});

it("completes tour and sets localStorage on Skip", () => {
  renderTour();
  fireEvent.click(screen.getByText("tour.skip"));
  expect(localStorage.getItem(TOUR_STORAGE_KEY)).toBe("true");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("shows Done button on last step and completes tour", () => {
  renderTour();
  // Advance to last step (step 3 = index 2)
  fireEvent.click(screen.getByText("tour.next")); // step 2
  fireEvent.click(screen.getByText("tour.next")); // step 3
  // Now on last step, button should say "Done"
  expect(screen.getByText("tour.done")).toBeInTheDocument();
  fireEvent.click(screen.getByText("tour.done"));
  expect(localStorage.getItem(TOUR_STORAGE_KEY)).toBe("true");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("skips tour on Escape key", () => {
  renderTour();
  fireEvent.keyDown(document, { key: "Escape" });
  expect(localStorage.getItem(TOUR_STORAGE_KEY)).toBe("true");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("advances on ArrowRight key", () => {
  renderTour();
  fireEvent.keyDown(document, { key: "ArrowRight" });
  expect(screen.getByText("tour.step2.title")).toBeInTheDocument();
});

it("goes back on ArrowLeft key when not on first step", () => {
  renderTour();
  fireEvent.keyDown(document, { key: "ArrowRight" });
  fireEvent.keyDown(document, { key: "ArrowLeft" });
  expect(screen.getByText("tour.step1.title")).toBeInTheDocument();
});
