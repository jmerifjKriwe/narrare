/**
 * Conceptual tour steps (CR-07 v3 Phase B / CR-AUFG-07-17).
 *
 * Verifies that FEATURE_TOUR_STEPS exposes three new conceptual entries
 * (steps 7, 8, 9) alongside the six existing UI-walkthrough steps, that
 * each new step uses a centered tooltip (no DOM target), and that the
 * FeatureTour component renders nine step indicator dots.
 */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it } from "vitest";
import { FeatureTour, requestFeatureTour, TOUR_STORAGE_KEY } from "@/components/ui/feature-tour";
import { FEATURE_TOUR_STEPS } from "@/lib/config/feature-tour-steps";

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  cleanup();
});

it("exposes nine tour steps total (six existing + three conceptual)", () => {
  expect(FEATURE_TOUR_STEPS).toHaveLength(9);
});

it.each([
  {
    descriptionKey: "tour.step7.description",
    index: 6,
    titleKey: "tour.step7.title",
  },
  {
    descriptionKey: "tour.step8.description",
    index: 7,
    titleKey: "tour.step8.title",
  },
  {
    descriptionKey: "tour.step9.description",
    index: 8,
    titleKey: "tour.step9.title",
  },
] as const)(
  "step at index $index uses centered tooltip and references $titleKey / $descriptionKey",
  ({ descriptionKey, index, titleKey }) => {
    const step = FEATURE_TOUR_STEPS[index];

    expect(step.target).toBeUndefined();
    expect(step.titleKey).toBe(titleKey);
    expect(step.descriptionKey).toBe(descriptionKey);
  },
);

it("FeatureTour renders nine step indicator dots", () => {
  render(<FeatureTour steps={FEATURE_TOUR_STEPS} />);
  const dialog = screen.getByRole("dialog");
  const dots = dialog.querySelectorAll(".rounded-full");
  expect(dots).toHaveLength(9);
});

it("replaying the tour from settings surfaces all nine steps including conceptual ones", async () => {
  localStorage.setItem(TOUR_STORAGE_KEY, "true");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

  requestFeatureTour();
  render(<FeatureTour steps={FEATURE_TOUR_STEPS} />);

  await waitFor(() => {
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  for (let i = 0; i < 6; i += 1) {
    fireEvent.click(screen.getByRole("button", { name: /next/i }));
  }

  expect(screen.getByText("tour.step7.title")).toBeInTheDocument();
});
