# Motion Activation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Activate the motion (Framer Motion) library across all Narrare frontend components that lack animation, and migrate the sole tw-animate-css usage to motion.

**Architecture:** Centralized animation variants in `lib/motion-variants.ts` provide all shared motion configurations. Components import variants and wrap conditional content with `AnimatePresence` + `motion.div`. Radix-based dialogs use CSS `@starting-style` for enter animations (Radix controls mount lifecycle internally). All animations respect `prefers-reduced-motion`.

**Tech Stack:** motion v12.42.2 (already installed), React 19, Next.js 16, Tailwind CSS v4, Radix UI

## Global Constraints

- motion v12.42.2 — imports from `motion/react`, NOT `framer-motion`
- All animations use shared variants from `lib/motion-variants.ts` — no inline variant objects
- `prefers-reduced-motion` must be respected via `useReducedMotion()` hook
- Tailwind CSS `transition-*` classes remain for simple hover effects — motion augments, does not replace
- `@dnd-kit` remains for drag-and-drop — motion's Draggable is NOT used
- `sonner` remains for toast animations — NOT replaced by motion
- tw-animate-css is removed after Phase 1 migration
- File size limit (RULE-04): `motion-variants.ts` max 150 lines; individual components must not grow beyond existing limits

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `packages/web/lib/motion-variants.ts` | All shared animation variant objects (overlay, dialog, panel, list, banner) |
| `packages/web/lib/hooks/use-reduced-motion.ts` | Thin wrapper around motion's `useReducedMotion` with Narrare defaults |
| `packages/web/components/ui/phase-crossfade.tsx` | Shared wrapper for phase/view transitions (`AnimatePresence mode="wait"`) |

### Modified Files (by phase)

| Phase | Files |
|-------|-------|
| 1 | `confirm-dialog.tsx`, `GhostTextOnboarding.tsx`, `tailwind.css`, `package.json` |
| 2 | 11 modal/dialog components (see Tasks 4-14) |
| 3 | `panel-shell.tsx`, `GenerationPanel.tsx`, `SessionPanel.tsx`, `ChatPanel.tsx`, `UnblockPanel.tsx`, 9 analysis panels |
| 4 | `NovelCardGrid.tsx`, `ChatPanel.tsx`, `SessionPanel.tsx`, `KBEntryList.tsx`, `RewriteSuggestionList.tsx`, `UnblockResults.tsx`, `VolumeCard.tsx` |
| 5 | `SessionReconnectBanner.tsx`, `connection-lost-banner.tsx`, `status-message.tsx`, `GenerationPanel.tsx`, `SessionPanel.tsx` |
| 6 | `NovelCardGrid.tsx`, `EditorStates.tsx`, `feature-tour.tsx` |

---

## Phase 1 — Foundation

### Task 1: Create motion variants library

**Files:**
- Create: `packages/web/lib/motion-variants.ts`

**Interfaces:**
- Consumes: motion/react types (`Variants`, `Transition`)
- Produces: `overlayVariants`, `dialogVariants`, `panelSlideRightVariants`, `panelSlideBottomVariants`, `listContainerVariants`, `listItemVariants`, `bannerSlideVariants`, `crossfadeVariants`, `DURATION`, `EASING`

- [ ] **Step 1: Create the variants file**

```typescript
// packages/web/lib/motion-variants.ts
import type { Variants, Transition } from "motion/react";

// --- Duration / Easing constants ---
export const DURATION = {
  fast: 0.15,
  normal: 0.2,
  slow: 0.3,
} as const;

export const EASING = {
  easeOut: [0, 0, 0.2, 1],
  easeIn: [0.4, 0, 1, 1],
  easeInOut: [0.4, 0, 0.2, 1],
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

// --- 4. Panel Slide (Mobile: from bottom) ---
export const panelSlideBottomVariants: Variants = {
  hidden: { y: "100%", opacity: 0 },
  visible: { y: 0, opacity: 1, transition: defaultTransition },
  exit: { y: "100%", opacity: 0, transition: { duration: DURATION.fast } },
};

// --- 5. List Container (stagger parent) ---
export const listContainerVariants: Variants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.05 },
  },
};

// --- 6. List Item (fade + slide up) ---
export const listItemVariants: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: { opacity: 1, y: 0, transition: defaultTransition },
  exit: { opacity: 0, y: -8, transition: { duration: DURATION.fast } },
};

// --- 7. Banner Slide (from top) ---
export const bannerSlideVariants: Variants = {
  hidden: { opacity: 0, y: -20 },
  visible: { opacity: 1, y: 0, transition: defaultTransition },
  exit: { opacity: 0, y: -20, transition: { duration: DURATION.fast } },
};

// --- 8. Crossfade (for phase transitions) ---
export const crossfadeVariants: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: defaultTransition },
  exit: { opacity: 0, transition: { duration: DURATION.fast } },
};
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd packages/web && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: No errors related to `motion-variants.ts`

- [ ] **Step 3: Commit**

```bash
git add packages/web/lib/motion-variants.ts
git commit -m "feat(web): add shared motion animation variants library"
```

---

### Task 2: Create useReducedMotion hook

**Files:**
- Create: `packages/web/lib/hooks/use-reduced-motion.ts`

**Interfaces:**
- Consumes: `useReducedMotion` from `motion/react`
- Produces: `useReducedMotion()` — returns `boolean`, defaults to `false`

- [ ] **Step 1: Create the hook**

```typescript
// packages/web/lib/hooks/use-reduced-motion.ts
"use client";

import { useReducedMotion as motionUseReducedMotion } from "motion/react";

/**
 * Wrapper around motion's useReducedMotion.
 * Returns true when the user prefers reduced motion.
 * Falls back to false (animations enabled) if the hook is unavailable.
 */
export function useReducedMotion(): boolean {
  const prefersReduced = motionUseReducedMotion();
  return prefersReduced ?? false;
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd packages/web && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add packages/web/lib/hooks/use-reduced-motion.ts
git commit -m "feat(web): add useReducedMotion hook wrapper"
```

---

### Task 3: Create PhaseCrossfade wrapper component

**Files:**
- Create: `packages/web/components/ui/phase-crossfade.tsx`

**Interfaces:**
- Consumes: `crossfadeVariants` from `lib/motion-variants.ts`, `AnimatePresence` + `motion.div` from `motion/react`
- Produces: `<PhaseCrossfade phase={key}>` — wraps content with crossfade animation on phase change

- [ ] **Step 1: Create the component**

```tsx
// packages/web/components/ui/phase-crossfade.tsx
"use client";

import { AnimatePresence, motion } from "motion/react";
import { crossfadeVariants } from "~/lib/motion-variants";

interface PhaseCrossfadeProps {
  /** Unique key for the current phase — triggers exit/enter animation on change */
  phase: string;
  children: React.ReactNode;
}

/**
 * Wraps content with crossfade animation when `phase` changes.
 * Usage:
 *   <PhaseCrossfade phase={currentPhase}>
 *     <div>Phase content here</div>
 *   </PhaseCrossfade>
 */
export function PhaseCrossfade({ phase, children }: PhaseCrossfadeProps) {
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={phase}
        variants={crossfadeVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
        className="h-full"
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd packages/web && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add packages/web/components/ui/phase-crossfade.tsx
git commit -m "feat(web): add PhaseCrossfade wrapper component"
```

---

### Task 4: Migrate ConfirmDialog from tw-animate-css to motion

**Files:**
- Modify: `packages/web/components/ui/confirm-dialog.tsx` (lines 53-54: replace tw-animate-css classes)

**Interfaces:**
- Consumes: `overlayVariants`, `dialogVariants` from `lib/motion-variants.ts`
- Produces: ConfirmDialog with motion-based enter/exit animations (visually identical to current)

- [ ] **Step 1: Read the current file**

Read: `packages/web/components/ui/confirm-dialog.tsx`
Note the tw-animate-css classes on lines 53-54:
- Overlay: `data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0`
- Content: `data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95`

- [ ] **Step 2: Migrate to motion**

Replace the tw-animate-css classes with motion's `style` prop using CSS `@starting-style` for Radix enter animations. Radix controls mount/unmount internally, so we use CSS animations (not AnimatePresence):

```tsx
// Add import at top of file:
import { motion } from "motion/react";
import { overlayVariants, dialogVariants } from "~/lib/motion-variants";

// On AlertDialog.Overlay — replace tw-animate-css classes with:
// Remove: data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0
// Add style prop:
style={{
  // Enter via @starting-style (Radix renders then animates)
  animation: "none",
}}
className="..."
// Add CSS animation via data-state:
// Use the motion variants approach: apply initial/animate via CSS

// ACTUAL APPROACH for Radix:
// Since Radix AlertDialog manages its own mount/unmount,
// we use CSS @starting-style for enter and data-[state] for exit.
// Replace overlay classes with:
className="fixed inset-0 z-50 bg-black/50 data-[state=open]:animate-[overlayShow_0.2s_ease-out] data-[state=closed]:animate-[overlayHide_0.15s_ease-in]"

// Replace content classes with:
className="... data-[state=open]:animate-[dialogShow_0.2s_ease-out] data-[state=closed]:animate-[dialogHide_0.15s_ease-in]"
```

**Wait — this approach creates inline keyframes.** The cleaner approach for Radix is to keep CSS `@keyframes` in a global stylesheet (or the component's scope) and reference them via `data-[state]`. This is actually the pattern that tw-animate-css uses under the hood. Let me revise:

**Revised approach:** Define `@keyframes` in `styles/tailwind.css` (replacing tw-animate-css's keyframes) and reference them via Tailwind's `animate-[...]` utility:

```css
/* Add to styles/tailwind.css after removing tw-animate-css import */
@keyframes overlay-show {
  from { opacity: 0; }
  to { opacity: 1; }
}
@keyframes overlay-hide {
  from { opacity: 1; }
  to { opacity: 0; }
}
@keyframes dialog-show {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}
@keyframes dialog-hide {
  from { opacity: 1; transform: scale(1); }
  to { opacity: 0; transform: scale(0.95); }
}
```

Then in confirm-dialog.tsx:
- Overlay: `data-[state=open]:animate-[overlay-show_0.2s_ease-out] data-[state=closed]:animate-[overlay-hide_0.15s_ease-in]`
- Content: `data-[state=open]:animate-[dialog-show_0.2s_ease-out] data-[state=closed]:animate-[dialog-hide_0.15s_ease-in]`

- [ ] **Step 3: Apply the changes**

In `confirm-dialog.tsx`:
1. Remove the tw-animate-css classes from `AlertDialog.Overlay` (line 53)
2. Remove the tw-animate-css classes from `AlertDialog.Content` (line 54)
3. Add the new `data-[state]` animation classes

- [ ] **Step 4: Verify visually**

Run: `cd packages/web && npm run dev`
Open a ConfirmDialog — verify fade-in on open, fade-out on close, scale animation on content.

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/ui/confirm-dialog.tsx
git commit -m "feat(web): migrate ConfirmDialog from tw-animate-css to motion keyframes"
```

---

### Task 5: Migrate GhostTextOnboarding and remove tw-animate-css

**Files:**
- Modify: `packages/web/components/studio/editor/GhostTextOnboarding.tsx` (line 66: replace `animate-in fade-in`)
- Modify: `packages/web/styles/tailwind.css` (remove `@import 'tw-animate-css'`, add custom keyframes)
- Modify: `packages/web/package.json` (remove `tw-animate-css` dependency)

**Interfaces:**
- Consumes: Custom `@keyframes` added in Task 4 Step 2
- Produces: No tw-animate-css imports anywhere in codebase

- [ ] **Step 1: Read GhostTextOnboarding.tsx**

Read: `packages/web/components/studio/editor/GhostTextOnboarding.tsx`
Note line 66: `className="... animate-in fade-in duration-300 ..."`

- [ ] **Step 2: Replace tw-animate-css class in GhostTextOnboarding**

Replace `animate-in fade-in duration-300` with `animate-[overlay-show_0.3s_ease-out]` (reusing the keyframe from Task 4).

- [ ] **Step 3: Update tailwind.css**

Replace:
```css
@import 'tw-animate-css';
```
With the custom keyframes defined in Task 4 Step 2 (overlay-show, overlay-hide, dialog-show, dialog-hide).

- [ ] **Step 4: Remove tw-animate-css from package.json**

Remove `"tw-animate-css": "^1.4.0"` from `dependencies` in `packages/web/package.json`.

- [ ] **Step 5: Run package manager**

Run: `cd packages/web && npm install` (or the project's package manager) to update lockfile.

- [ ] **Step 6: Verify no remaining tw-animate-css references**

Run: `grep -r "tw-animate-css" packages/web/`
Expected: No results

- [ ] **Step 7: Verify ConfirmDialog and GhostTextOnboarding still animate**

Run: `cd packages/web && npm run dev`
Test both components visually.

- [ ] **Step 8: Commit**

```bash
git add packages/web/components/studio/editor/GhostTextOnboarding.tsx packages/web/styles/tailwind.css packages/web/package.json
git commit -m "feat(web): remove tw-animate-css, migrate to custom motion keyframes"
```

---

## Phase 2 — Modals (11 components)

Each modal follows the same pattern:
1. Remove early `return null` (keep the condition, but render AnimatePresence instead)
2. Wrap root element with `<AnimatePresence>`
3. Replace plain `<div>` with `<motion.div>` using `overlayVariants` + `dialogVariants`
4. Import from `motion/react` and `~/lib/motion-variants`

**Shared pattern for all modals:**

```tsx
import { AnimatePresence, motion } from "motion/react";
import { overlayVariants, dialogVariants } from "~/lib/motion-variants";

// Before: if (!open) return null;
// After:
return (
  <AnimatePresence>
    {open && (
      <motion.div
        variants={overlayVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
        className="fixed inset-0 z-50 bg-black/50 ..."
      >
        <motion.div
          variants={dialogVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          className="..."
        >
          {/* dialog content */}
        </motion.div>
      </motion.div>
    )}
  </AnimatePresence>
);
```

### Task 6: Animate RewriteSuggestionModal

**Files:**
- Modify: `packages/web/components/studio/editor/RewriteSuggestionModal.tsx`

**Interfaces:**
- Consumes: `AnimatePresence`, `motion` from `motion/react`; `overlayVariants`, `dialogVariants` from `~/lib/motion-variants`
- Produces: Modal with fade-in/fade-out overlay and scale-in/scale-out dialog

- [ ] **Step 1: Read the current file**

Read: `packages/web/components/studio/editor/RewriteSuggestionModal.tsx`

- [ ] **Step 2: Add motion imports**

Add to imports:
```tsx
import { AnimatePresence, motion } from "motion/react";
import { overlayVariants, dialogVariants } from "~/lib/motion-variants";
```

- [ ] **Step 3: Wrap return with AnimatePresence**

The component is controlled by `aiSuggestion` prop (not a boolean `open`). Wrap the entire return:

```tsx
return (
  <AnimatePresence>
    {aiSuggestion && (
      <motion.div
        variants={overlayVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
        className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4"
      >
        <motion.div
          variants={dialogVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          className="relative w-full max-w-lg ..."
        >
          {/* existing dialog content, unchanged */}
        </motion.div>
      </motion.div>
    )}
  </AnimatePresence>
);
```

- [ ] **Step 4: Verify TypeScript compiles**

Run: `cd packages/web && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/studio/editor/RewriteSuggestionModal.tsx
git commit -m "feat(web): add enter/exit animation to RewriteSuggestionModal"
```

---

### Task 7: Animate CommandPalette

**Files:**
- Modify: `packages/web/components/studio/editor/CommandPalette.tsx` (line 121: `if (!isOpen) return null`)

**Interfaces:**
- Same as Task 6 pattern
- `open` is a boolean prop

- [ ] **Step 1: Read the current file**

Read: `packages/web/components/studio/editor/CommandPalette.tsx`

- [ ] **Step 2: Add motion imports**

```tsx
import { AnimatePresence, motion } from "motion/react";
import { overlayVariants, dialogVariants } from "~/lib/motion-variants";
```

- [ ] **Step 3: Replace early return with AnimatePresence**

Remove line 121 (`if (!isOpen) return null;`). Wrap return:

```tsx
return (
  <AnimatePresence>
    {isOpen && (
      <motion.div
        variants={overlayVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
        className="fixed inset-0 z-50 ..."
      >
        <motion.div
          variants={dialogVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          className="..."
        >
          {/* existing content */}
        </motion.div>
      </motion.div>
    )}
  </AnimatePresence>
);
```

- [ ] **Step 4: Verify TypeScript compiles**

Run: `cd packages/web && npx tsc --noEmit --pretty 2>&1 | head -20`

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/studio/editor/CommandPalette.tsx
git commit -m "feat(web): add enter/exit animation to CommandPalette"
```

---

### Task 8: Animate CoAuthorPanel

**Files:**
- Modify: `packages/web/components/studio/editor/CoAuthorPanel.tsx`

**Interfaces:**
- Same modal pattern. CoAuthorPanel is always rendered (parent controls via phase). Wrap the entire return.

- [ ] **Step 1: Read the current file**

Read: `packages/web/components/studio/editor/CoAuthorPanel.tsx`

- [ ] **Step 2: Add motion imports and wrap return**

Add imports. The panel renders unconditionally — wrap the fixed overlay div:

```tsx
return (
  <AnimatePresence>
    <motion.div
      variants={overlayVariants}
      initial="hidden"
      animate="visible"
      exit="exit"
      className="fixed inset-0 z-50 bg-black/50 ..."
    >
      <motion.div
        variants={dialogVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
        className="..."
      >
        {/* existing phase content */}
      </motion.div>
    </motion.div>
  </AnimatePresence>
);
```

- [ ] **Step 3: Verify TypeScript compiles**

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/studio/editor/CoAuthorPanel.tsx
git commit -m "feat(web): add enter/exit animation to CoAuthorPanel"
```

---

### Task 9: Animate PromptPreviewDialog

**Files:**
- Modify: `packages/web/components/studio/settings/PromptPreviewDialog.tsx` (line 50: `if (!open) return null`)

- [ ] **Step 1: Read the current file**

- [ ] **Step 2: Add motion imports, replace early return with AnimatePresence pattern**

Remove `if (!open) return null;`. Wrap return with `AnimatePresence` + `motion.div` using `overlayVariants` + `dialogVariants`.

- [ ] **Step 3: Verify TypeScript compiles**

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/studio/settings/PromptPreviewDialog.tsx
git commit -m "feat(web): add enter/exit animation to PromptPreviewDialog"
```

---

### Task 10: Animate PromptResetConfirmDialog

**Files:**
- Modify: `packages/web/components/studio/settings/PromptResetConfirmDialog.tsx` (line 45: `if (!open) return null`)

- [ ] **Step 1: Read the current file**

- [ ] **Step 2: Add motion imports, replace early return with AnimatePresence pattern**

Same pattern as Task 9.

- [ ] **Step 3: Verify TypeScript compiles**

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/studio/settings/PromptResetConfirmDialog.tsx
git commit -m "feat(web): add enter/exit animation to PromptResetConfirmDialog"
```

---

### Task 11: Animate PromptLiveTestDialog

**Files:**
- Modify: `packages/web/components/studio/settings/PromptLiveTestDialog.tsx` (line 72: `if (!open) return null`)

- [ ] **Step 1: Read the current file**

- [ ] **Step 2: Add motion imports, replace early return with AnimatePresence pattern**

Same pattern as Task 9.

- [ ] **Step 3: Verify TypeScript compiles**

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/studio/settings/PromptLiveTestDialog.tsx
git commit -m "feat(web): add enter/exit animation to PromptLiveTestDialog"
```

---

### Task 12: Animate ToneFormDialog

**Files:**
- Modify: `packages/web/components/studio/settings/ToneFormDialog.tsx`

**Interfaces:**
- ToneFormDialog renders unconditionally (parent controls via `tone` prop). Wrap the fixed overlay.

- [ ] **Step 1: Read the current file**

- [ ] **Step 2: Add motion imports, wrap return with AnimatePresence**

```tsx
return (
  <AnimatePresence>
    <motion.div
      variants={overlayVariants}
      initial="hidden"
      animate="visible"
      exit="exit"
      className="fixed inset-0 z-50 ..."
    >
      <motion.div
        variants={dialogVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
        className="..."
      >
        {/* existing content */}
      </motion.div>
    </motion.div>
  </AnimatePresence>
);
```

- [ ] **Step 3: Verify TypeScript compiles**

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/studio/settings/ToneFormDialog.tsx
git commit -m "feat(web): add enter/exit animation to ToneFormDialog"
```

---

### Task 13: Animate ExtractionPanel

**Files:**
- Modify: `packages/web/components/studio/extraction/ExtractionPanel.tsx`

**Interfaces:**
- Parent uses `{extractionPanelOpen && <ExtractionPanel>}` — so AnimatePresence goes in the parent (`EditorOverlays.tsx` line 51), or the component wraps itself.

- [ ] **Step 1: Read ExtractionPanel.tsx and EditorOverlays.tsx**

- [ ] **Step 2: Add AnimatePresence in EditorOverlays.tsx around the conditional render**

```tsx
// In EditorOverlays.tsx, around line 51:
<AnimatePresence>
  {extractionPanelOpen && <ExtractionPanel onClose={...} />}
</AnimatePresence>
```

Then in ExtractionPanel.tsx, wrap the overlay div with `motion.div` using `overlayVariants` + `dialogVariants`.

- [ ] **Step 3: Verify TypeScript compiles**

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/studio/extraction/ExtractionPanel.tsx packages/web/components/studio/editor/EditorOverlays.tsx
git commit -m "feat(web): add enter/exit animation to ExtractionPanel"
```

---

### Task 14: Animate AddRelationshipDialog

**Files:**
- Modify: `packages/web/components/studio/kb/AddRelationshipDialog.tsx`

- [ ] **Step 1: Read the current file**

- [ ] **Step 2: Add motion imports, wrap return with AnimatePresence + motion.div**

Same pattern as Task 6.

- [ ] **Step 3: Verify TypeScript compiles**

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/studio/kb/AddRelationshipDialog.tsx
git commit -m "feat(web): add enter/exit animation to AddRelationshipDialog"
```

---

### Task 15: Animate StructureChangeDialog

**Files:**
- Modify: `packages/web/components/studio/planning/StructureChangeDialog.tsx` (line 38: `if (!open) return null`)

- [ ] **Step 1: Read the current file**

- [ ] **Step 2: Add motion imports, replace early return with AnimatePresence pattern**

Same pattern as Task 7.

- [ ] **Step 3: Verify TypeScript compiles**

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/studio/planning/StructureChangeDialog.tsx
git commit -m "feat(web): add enter/exit animation to StructureChangeDialog"
```

---

### Task 16: Animate NameGeneratorModal

**Files:**
- Modify: `packages/web/components/studio/generation/NameGeneratorModal.tsx` (line 38: `if (!isOpen) return null`, line 56: existing `animate-[narrare-slide-left_0.25s_ease-out]`)

**Interfaces:**
- Has existing CSS animation (`narrare-slide-left`) that needs migration to motion.

- [ ] **Step 1: Read the current file**

- [ ] **Step 2: Add motion imports, replace early return with AnimatePresence**

Remove the `animate-[narrare-slide-left_0.25s_ease-out]` class. Replace with `motion.div` using `panelSlideRightVariants`:

```tsx
<AnimatePresence>
  {isOpen && (
    <motion.div
      variants={overlayVariants}
      initial="hidden"
      animate="visible"
      exit="exit"
      className="fixed inset-0 z-50 ..."
    >
      <motion.div
        variants={panelSlideRightVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
        className="..."
      >
        {/* existing content */}
      </motion.div>
    </motion.div>
  )}
</AnimatePresence>
```

- [ ] **Step 3: Verify TypeScript compiles**

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/studio/generation/NameGeneratorModal.tsx
git commit -m "feat(web): migrate NameGeneratorModal from CSS to motion animation"
```

---

## Phase 3 — Panels

### Task 17: Add slide animation to PanelShell

**Files:**
- Modify: `packages/web/components/ui/panel-shell.tsx` (line 55: `if (!open) return null`)

**Interfaces:**
- Consumes: `AnimatePresence`, `motion` from `motion/react`; `panelSlideRightVariants`, `panelSlideBottomVariants` from `~/lib/motion-variants`; `useReducedMotion` from `~/lib/hooks/use-reduced-motion`
- Produces: PanelShell with slide-in from right (desktop) / bottom (mobile)

- [ ] **Step 1: Read the current file**

Read: `packages/web/components/ui/panel-shell.tsx`

- [ ] **Step 2: Add imports and hook**

```tsx
import { AnimatePresence, motion } from "motion/react";
import { panelSlideRightVariants, panelSlideBottomVariants } from "~/lib/motion-variants";
import { useReducedMotion } from "~/lib/hooks/use-reduced-motion";
```

- [ ] **Step 3: Replace early return with AnimatePresence**

Remove `if (!open) return null;` (line 55). Add reduced motion check. Wrap the `<section>` with motion:

```tsx
const reducedMotion = useReducedMotion();

return (
  <AnimatePresence>
    {open && (
      <motion.section
        variants={reducedMotion ? undefined : (isDesktop ? panelSlideRightVariants : panelSlideBottomVariants)}
        initial={reducedMotion ? undefined : "hidden"}
        animate={reducedMotion ? undefined : "visible"}
        exit={reducedMotion ? undefined : "exit"}
        className={SHELL_CLASSES}
        style={desktopBorder ? { borderLeft: "1px solid var(--border)" } : undefined}
      >
        {children}
      </motion.section>
    )}
  </AnimatePresence>
);
```

Note: `isDesktop` needs to be determined. Check if PanelShell already has responsive logic. If not, use `window.matchMedia` or a Tailwind approach. The simplest is to always use `panelSlideRightVariants` since PanelShell is primarily a desktop sidebar.

- [ ] **Step 4: Verify TypeScript compiles**

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/ui/panel-shell.tsx
git commit -m "feat(web): add slide animation to PanelShell"
```

---

### Task 18: Add phase crossfade to GenerationPanel

**Files:**
- Modify: `packages/web/components/studio/editor/GenerationPanel.tsx` (lines 75-162: phase conditional swaps)

**Interfaces:**
- Consumes: `PhaseCrossfade` from `~/components/ui/phase-crossfade`
- Produces: GenerationPanel with smooth crossfade between config/streaming/review/error phases

- [ ] **Step 1: Read the current file**

Read: `packages/web/components/studio/editor/GenerationPanel.tsx`

- [ ] **Step 2: Add PhaseCrossfade import**

```tsx
import { PhaseCrossfade } from "~/components/ui/phase-crossfade";
```

- [ ] **Step 3: Wrap phase content with PhaseCrossfade**

Replace the conditional phase rendering block (lines 75-162) with:

```tsx
<PhaseCrossfade phase={controller.phase}>
  {controller.phase === "config" && (
    <div>/* config content */</div>
  )}
  {(controller.phase === "streaming" || controller.phase === "review") && (
    <div>/* streaming/review content */</div>
  )}
  {controller.phase === "error" && (
    <div>/* error content */</div>
  )}
</PhaseCrossfade>
```

- [ ] **Step 4: Verify TypeScript compiles**

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/studio/editor/GenerationPanel.tsx
git commit -m "feat(web): add phase crossfade to GenerationPanel"
```

---

### Task 19: Add phase crossfade to SessionPanel and ChatPanel

**Files:**
- Modify: `packages/web/components/studio/editor/SessionPanel.tsx`
- Modify: `packages/web/components/studio/editor/ChatPanel.tsx`

- [ ] **Step 1: Read both files**

- [ ] **Step 2: Add PhaseCrossfade to SessionPanel**

Wrap the message list area with `PhaseCrossfade` if there are distinct phases, or add `motion.div` with `listItemVariants` to individual messages.

- [ ] **Step 3: Add PhaseCrossfade to ChatPanel**

Same pattern as SessionPanel.

- [ ] **Step 4: Verify TypeScript compiles**

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/studio/editor/SessionPanel.tsx packages/web/components/studio/editor/ChatPanel.tsx
git commit -m "feat(web): add phase crossfade to SessionPanel and ChatPanel"
```

---

### Task 20: Create shared AnalysisPanel wrapper

**Files:**
- Create: `packages/web/components/ui/analysis-panel-wrapper.tsx`

**Interfaces:**
- Consumes: `PhaseCrossfade` from `~/components/ui/phase-crossfade`
- Produces: `<AnalysisPanelWrapper phase={phase}>` — wraps analysis panel content with crossfade

- [ ] **Step 1: Create the wrapper**

```tsx
// packages/web/components/ui/analysis-panel-wrapper.tsx
"use client";

import { PhaseCrossfade } from "./phase-crossfade";

interface AnalysisPanelWrapperProps {
  phase: string;
  children: React.ReactNode;
}

/**
 * Shared wrapper for analysis panels (BetaReader, Consistency, POV, etc.).
 * Adds crossfade animation between idle/loading/results/error phases.
 */
export function AnalysisPanelWrapper({ phase, children }: AnalysisPanelWrapperProps) {
  return <PhaseCrossfade phase={phase}>{children}</PhaseCrossfade>;
}
```

- [ ] **Step 2: Verify TypeScript compiles**

- [ ] **Step 3: Commit**

```bash
git add packages/web/components/ui/analysis-panel-wrapper.tsx
git commit -m "feat(web): add shared AnalysisPanelWrapper with phase crossfade"
```

---

### Task 21: Apply AnalysisPanelWrapper to all analysis panels

**Files:**
- Modify: `packages/web/components/studio/analysis/BetaReaderPanel.tsx`
- Modify: `packages/web/components/studio/analysis/CharacterVoicePanel.tsx`
- Modify: `packages/web/components/studio/analysis/ConsistencyPanel.tsx`
- Modify: `packages/web/components/studio/analysis/CoreferencePanel.tsx`
- Modify: `packages/web/components/studio/analysis/POVPanel.tsx`
- Modify: `packages/web/components/studio/analysis/ReadabilityPanel.tsx`
- Modify: `packages/web/components/studio/analysis/SentimentPanel.tsx`
- Modify: `packages/web/components/studio/analysis/VoiceCheckPanel.tsx`
- Modify: `packages/web/components/studio/analysis/DialogueCoachPanel.tsx`

**Interfaces:**
- Consumes: `AnalysisPanelWrapper` from `~/components/ui/analysis-panel-wrapper`
- Each panel has a `phase` state (idle/loading/results/error)

- [ ] **Step 1: Read one analysis panel to understand the pattern**

Read: `packages/web/components/studio/analysis/BetaReaderPanel.tsx`

- [ ] **Step 2: Apply wrapper to BetaReaderPanel**

```tsx
import { AnalysisPanelWrapper } from "~/components/ui/analysis-panel-wrapper";

// Wrap the phase content:
<AnalysisPanelWrapper phase={phase}>
  {phase === "idle" && <div>/* idle */</div>}
  {phase === "loading" && <div>/* loading */</div>}
  {phase === "results" && <div>/* results */</div>}
  {phase === "error" && <div>/* error */</div>}
</AnalysisPanelWrapper>
```

- [ ] **Step 3: Apply same pattern to remaining 8 analysis panels**

Read each panel, find the phase conditional block, wrap with `AnalysisPanelWrapper`.

- [ ] **Step 4: Verify TypeScript compiles**

Run: `cd packages/web && npx tsc --noEmit --pretty 2>&1 | head -30`

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/studio/analysis/*.tsx
git commit -m "feat(web): add phase crossfade to all 9 analysis panels"
```

---

### Task 22: Add slide animation to UnblockPanel

**Files:**
- Modify: `packages/web/components/studio/editor/UnblockPanel.tsx`

**Interfaces:**
- Consumes: `AnimatePresence`, `motion` from `motion/react`; `panelSlideRightVariants` from `~/lib/motion-variants`

- [ ] **Step 1: Read the current file**

- [ ] **Step 2: Add motion imports and wrap with AnimatePresence**

The panel toggles between a button and a fixed panel. Wrap the panel portion with `motion.div` using `panelSlideRightVariants`.

- [ ] **Step 3: Verify TypeScript compiles**

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/studio/editor/UnblockPanel.tsx
git commit -m "feat(web): add slide animation to UnblockPanel"
```

---

## Phase 4 — List Stagger Animations

### Task 23: Add stagger to NovelCardGrid

**Files:**
- Modify: `packages/web/components/studio/NovelCardGrid.tsx`

**Interfaces:**
- Consumes: `AnimatePresence`, `motion` from `motion/react`; `listContainerVariants`, `listItemVariants` from `~/lib/motion-variants`

- [ ] **Step 1: Read the current file**

- [ ] **Step 2: Add motion imports**

- [ ] **Step 3: Wrap grid with listContainerVariants, each card with listItemVariants**

```tsx
<motion.div
  variants={listContainerVariants}
  initial="hidden"
  animate="visible"
  className="grid grid-cols-1 ..."
>
  {novels.map((novel) => (
    <motion.div key={novel.id} variants={listItemVariants}>
      {/* existing NovelCard content */}
    </motion.div>
  ))}
</motion.div>
```

- [ ] **Step 4: Verify TypeScript compiles**

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/studio/NovelCardGrid.tsx
git commit -m "feat(web): add stagger animation to NovelCardGrid"
```

---

### Task 24: Add stagger to ChatMessage lists

**Files:**
- Modify: `packages/web/components/studio/editor/ChatPanel.tsx`
- Modify: `packages/web/components/studio/editor/SessionPanel.tsx`

- [ ] **Step 1: Read both files**

- [ ] **Step 2: Add list stagger to message rendering in ChatPanel**

Wrap the message list container with `listContainerVariants`, each message with `listItemVariants`.

- [ ] **Step 3: Add list stagger to SessionPanel**

Same pattern.

- [ ] **Step 4: Verify TypeScript compiles**

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/studio/editor/ChatPanel.tsx packages/web/components/studio/editor/SessionPanel.tsx
git commit -m "feat(web): add stagger animation to chat message lists"
```

---

### Task 25: Add stagger to KBEntryList

**Files:**
- Modify: `packages/web/components/studio/kb/KBEntryList.tsx`

- [ ] **Step 1: Read the current file**

- [ ] **Step 2: Add list stagger to entry card rendering**

Wrap entry list with `listContainerVariants`, each entry card with `listItemVariants`.

- [ ] **Step 3: Verify TypeScript compiles**

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/studio/kb/KBEntryList.tsx
git commit -m "feat(web): add stagger animation to KBEntryList"
```

---

### Task 26: Add stagger to RewriteSuggestionList and UnblockResults

**Files:**
- Modify: `packages/web/components/studio/editor/RewriteSuggestionList.tsx`
- Modify: `packages/web/components/studio/editor/UnblockResults.tsx`

- [ ] **Step 1: Read both files**

- [ ] **Step 2: Add list stagger to RewriteSuggestionList**

- [ ] **Step 3: Add list stagger to UnblockResults**

- [ ] **Step 4: Verify TypeScript compiles**

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/studio/editor/RewriteSuggestionList.tsx packages/web/components/studio/editor/UnblockResults.tsx
git commit -m "feat(web): add stagger animation to RewriteSuggestionList and UnblockResults"
```

---

### Task 27: Add stagger to VolumeCard

**Files:**
- Modify: `packages/web/components/studio/VolumeCard.tsx`

- [ ] **Step 1: Read the current file**

- [ ] **Step 2: Add list stagger to card rendering**

- [ ] **Step 3: Verify TypeScript compiles**

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/studio/VolumeCard.tsx
git commit -m "feat(web): add stagger animation to VolumeCard"
```

---

## Phase 5 — Banner/Notification Animations

### Task 28: Animate SessionReconnectBanner

**Files:**
- Modify: `packages/web/components/studio/editor/SessionReconnectBanner.tsx` (line 28: `if (recoveryState === "idle") return null`)

**Interfaces:**
- Consumes: `AnimatePresence`, `motion` from `motion/react`; `bannerSlideVariants` from `~/lib/motion-variants`

- [ ] **Step 1: Read the current file**

- [ ] **Step 2: Add motion imports, replace early return with AnimatePresence**

```tsx
return (
  <AnimatePresence>
    {recoveryState !== "idle" && (
      <motion.section
        variants={bannerSlideVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
        className="..."
      >
        {/* existing content */}
      </motion.section>
    )}
  </AnimatePresence>
);
```

- [ ] **Step 3: Verify TypeScript compiles**

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/studio/editor/SessionReconnectBanner.tsx
git commit -m "feat(web): add slide animation to SessionReconnectBanner"
```

---

### Task 29: Animate ConnectionLostBanner and StatusMessage

**Files:**
- Modify: `packages/web/components/ui/connection-lost-banner.tsx`
- Modify: `packages/web/components/ui/status-message.tsx`

**Interfaces:**
- `connection-lost-banner.tsx` wraps `StatusMessage` — animate at StatusMessage level for all consumers.

- [ ] **Step 1: Read both files**

- [ ] **Step 2: Add motion to StatusMessage**

Wrap the non-idle return of StatusMessage with `motion.div` using `bannerSlideVariants`:

```tsx
// In status-message.tsx, non-idle return:
return (
  <motion.div
    variants={bannerSlideVariants}
    initial="hidden"
    animate="visible"
    exit="exit"
    role={role}
    className="..."
  >
    {/* existing content */}
  </motion.div>
);
```

Note: `connection-lost-banner.tsx` doesn't need changes since it delegates to `StatusMessage`.

- [ ] **Step 3: Verify TypeScript compiles**

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/ui/status-message.tsx
git commit -m "feat(web): add slide animation to StatusMessage"
```

---

### Task 30: Animate inline banners in GenerationPanel and SessionPanel

**Files:**
- Modify: `packages/web/components/studio/editor/GenerationPanel.tsx` (line 148: connection lost banner)
- Modify: `packages/web/components/studio/editor/SessionPanel.tsx` (line 173: save notification)

- [ ] **Step 1: Read both files**

- [ ] **Step 2: Wrap inline banners with AnimatePresence + motion.div**

In GenerationPanel, wrap the connection lost bar:
```tsx
<AnimatePresence>
  {controller.connectionLost && (
    <motion.div
      variants={bannerSlideVariants}
      initial="hidden"
      animate="visible"
      exit="exit"
      className="..."
    >
      {/* connection lost content */}
    </motion.div>
  )}
</AnimatePresence>
```

In SessionPanel, wrap the save notification:
```tsx
<AnimatePresence>
  {saveNotification && (
    <motion.div
      variants={bannerSlideVariants}
      initial="hidden"
      animate="visible"
      exit="exit"
      className="..."
    >
      {/* save notification content */}
    </motion.div>
  )}
</AnimatePresence>
```

- [ ] **Step 3: Verify TypeScript compiles**

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/studio/editor/GenerationPanel.tsx packages/web/components/studio/editor/SessionPanel.tsx
git commit -m "feat(web): add slide animation to inline banners"
```

---

## Phase 6 — State Crossfade

### Task 31: Add skeleton-to-content crossfade in NovelCardGrid

**Files:**
- Modify: `packages/web/components/studio/NovelCardGrid.tsx` (lines 36-48: loading skeleton, line 60: content)

**Interfaces:**
- Consumes: `AnimatePresence` from `motion/react`; `crossfadeVariants` from `~/lib/motion-variants`

- [ ] **Step 1: Read the current file**

- [ ] **Step 2: Wrap loading/content states with AnimatePresence mode="wait"**

Replace the two early returns (`if (isLoading) return ...` and `if (novels.length === 0) return ...`) with a single return that uses `AnimatePresence mode="wait"`:

```tsx
return (
  <AnimatePresence mode="wait">
    {isLoading ? (
      <motion.div
        key="skeleton"
        variants={crossfadeVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
        className="grid grid-cols-1 ..."
      >
        {/* skeleton cards */}
      </motion.div>
    ) : novels.length === 0 ? (
      <motion.div
        key="empty"
        variants={crossfadeVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
      >
        {/* empty state */}
      </motion.div>
    ) : (
      <motion.div
        key="content"
        variants={crossfadeVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
        className="grid grid-cols-1 ..."
      >
        {/* card grid with stagger */}
      </motion.div>
    )}
  </AnimatePresence>
);
```

- [ ] **Step 3: Verify TypeScript compiles**

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/studio/NovelCardGrid.tsx
git commit -m "feat(web): add skeleton-to-content crossfade in NovelCardGrid"
```

---

### Task 32: Add editor loading state crossfade

**Files:**
- Modify: `packages/web/components/studio/editor-view/EditorStates.tsx`

**Interfaces:**
- Consumes: `AnimatePresence`, `motion` from `motion/react`; `crossfadeVariants` from `~/lib/motion-variants`

- [ ] **Step 1: Read the current file**

Read: `packages/web/components/studio/editor-view/EditorStates.tsx`

- [ ] **Step 2: Add motion imports and wrap loading state**

Wrap `EditorLoadingState` return with `motion.div` using `crossfadeVariants`:

```tsx
export function EditorLoadingState() {
  return (
    <motion.div
      variants={crossfadeVariants}
      initial="hidden"
      animate="visible"
      exit="exit"
      className="flex items-center justify-center h-full"
    >
      <div className="animate-pulse ...">
        {/* existing loading content */}
      </div>
    </motion.div>
  );
}
```

The parent (`EditorStates` or wherever loading/loaded switching happens) should wrap both states with `AnimatePresence mode="wait"`.

- [ ] **Step 3: Verify TypeScript compiles**

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/studio/editor-view/EditorStates.tsx
git commit -m "feat(web): add crossfade to editor loading state"
```

---

### Task 33: Add step transitions to FeatureTour

**Files:**
- Modify: `packages/web/components/ui/feature-tour.tsx` (lines 136-137: step content swaps)

**Interfaces:**
- Consumes: `AnimatePresence`, `motion` from `motion/react`; `crossfadeVariants` from `~/lib/motion-variants`

- [ ] **Step 1: Read the current file**

Read: `packages/web/components/ui/feature-tour.tsx`

- [ ] **Step 2: Add motion imports and wrap step content**

Wrap the tooltip content area with `AnimatePresence mode="wait"` and `motion.div` keyed by step index:

```tsx
<AnimatePresence mode="wait">
  <motion.div
    key={stepIndex}
    variants={crossfadeVariants}
    initial="hidden"
    animate="visible"
    exit="exit"
  >
    <h3>{step.title}</h3>
    <p>{step.description}</p>
  </motion.div>
</AnimatePresence>
```

- [ ] **Step 3: Verify TypeScript compiles**

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/ui/feature-tour.tsx
git commit -m "feat(web): add step crossfade transitions to FeatureTour"
```

---

## Verification

### Task 34: Full TypeScript check and visual QA

- [ ] **Step 1: Run full TypeScript check**

Run: `cd packages/web && npx tsc --noEmit --pretty`
Expected: Zero errors

- [ ] **Step 2: Run lint**

Run: `cd packages/web && npm run lint` (or project equivalent)
Expected: No new errors

- [ ] **Step 3: Run build**

Run: `cd packages/web && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Visual QA checklist**

Run: `cd packages/web && npm run dev`

Test each category:
- [ ] ConfirmDialog: Opens with fade+scale, closes with fade+scale
- [ ] RewriteSuggestionModal: Opens with fade+scale overlay
- [ ] CommandPalette: Opens with fade+scale
- [ ] PanelShell: Slides in from right
- [ ] GenerationPanel: Phase transitions crossfade smoothly
- [ ] NovelCardGrid: Cards stagger in, skeleton→content crossfades
- [ ] Chat messages: Stagger in
- [ ] SessionReconnectBanner: Slides down from top
- [ ] FeatureTour: Step content crossfades
- [ ] All analysis panels: Phase transitions crossfade
- [ ] `prefers-reduced-motion`: All animations disabled when OS setting is on

- [ ] **Step 5: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix(web): motion activation visual QA fixes"
```
