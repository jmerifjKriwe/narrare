import type { Transition, Variants } from "motion/react";

// --- Duration / Easing constants ---
export const DURATION = {
  fast: 0.15,
  normal: 0.2,
} as const;

export const EASING = {
  easeOut: [0, 0, 0.2, 1],
} as const;

const defaultTransition: Transition = {
  duration: DURATION.normal,
  ease: EASING.easeOut,
};

// --- 1. Overlay Fade ---
export const overlayVariants: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: defaultTransition },
  exit: { opacity: 0, transition: { duration: DURATION.fast } },
};

// --- 2. Dialog Enter/Exit (Fade + Scale) ---
export const dialogVariants: Variants = {
  hidden: { opacity: 0, scale: 0.95 },
  visible: { opacity: 1, scale: 1, transition: defaultTransition },
  exit: { opacity: 0, scale: 0.95, transition: { duration: DURATION.fast } },
};

// --- 3. Panel Slide (Desktop: from right) ---
export const panelSlideRightVariants: Variants = {
  hidden: { x: "100%", opacity: 0 },
  visible: { x: 0, opacity: 1, transition: defaultTransition },
  exit: { x: "100%", opacity: 0, transition: { duration: DURATION.fast } },
};

// --- 4. List Container (stagger parent) ---
export const listContainerVariants: Variants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.05 },
  },
};

// --- 5. List Item (fade + slide up) ---
export const listItemVariants: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: { opacity: 1, y: 0, transition: defaultTransition },
  exit: { opacity: 0, y: -8, transition: { duration: DURATION.fast } },
};

// --- 6. Banner Slide (from top) ---
export const bannerSlideVariants: Variants = {
  hidden: { opacity: 0, y: -20 },
  visible: { opacity: 1, y: 0, transition: defaultTransition },
  exit: { opacity: 0, y: -20, transition: { duration: DURATION.fast } },
};

// --- 7. Crossfade (for phase transitions) ---
export const crossfadeVariants: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: defaultTransition },
  exit: { opacity: 0, transition: { duration: DURATION.fast } },
};
