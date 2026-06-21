import type { TourStep } from "@/components/ui/feature-tour";

/**
 * Feature tour step definitions.
 *
 * Each step targets a CSS selector in the studio layout. When `target` is
 * omitted the tooltip is centered on screen (used for features that don't
 * have a persistent DOM element to highlight).
 *
 * All text is driven by i18n keys under `studio.tour.*`.
 */
export const FEATURE_TOUR_STEPS: TourStep[] = [
  {
    target: "main",
    titleKey: "tour.step1.title",
    descriptionKey: "tour.step1.description",
  },
  {
    target: "nav",
    titleKey: "tour.step2.title",
    descriptionKey: "tour.step2.description",
  },
  {
    // AI toolbar — no persistent selector, show centered
    titleKey: "tour.step3.title",
    descriptionKey: "tour.step3.description",
  },
  {
    // Ghost Text — dynamic, no persistent selector, show centered
    titleKey: "tour.step4.title",
    descriptionKey: "tour.step4.description",
  },
  {
    target: "a[href*='worldbuilding']",
    titleKey: "tour.step5.title",
    descriptionKey: "tour.step5.description",
  },
  {
    target: "a[href*='settings']",
    titleKey: "tour.step6.title",
    descriptionKey: "tour.step6.description",
  },
  {
    // Conceptual: KB → Context → AI (centered tooltip, no DOM target)
    titleKey: "tour.step7.title",
    descriptionKey: "tour.step7.description",
  },
  {
    // Conceptual: Storyboard → Chapter → AI
    titleKey: "tour.step8.title",
    descriptionKey: "tour.step8.description",
  },
  {
    // Conceptual: before/after demo moment
    titleKey: "tour.step9.title",
    descriptionKey: "tour.step9.description",
  },
];
