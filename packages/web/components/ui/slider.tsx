"use client";

import * as SliderPrimitive from "@radix-ui/react-slider";
import type * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Accessible range slider built on Radix Slider.
 *
 * Renders a `role="slider"` thumb that is fully keyboard-operable
 * (Arrow keys to nudge, Home/End to jump to the extremes). Pass an
 * `aria-label` (or `aria-labelledby`) so screen readers announce its
 * purpose — required by ui-principles §11. Radix manages the value-based
 * ARIA slider semantics (`aria-valuenow`/`valuemin`/`valuemax`) on the
 * thumb automatically.
 *
 * The accessible NAME is forwarded to the `<Thumb>` (the element carrying
 * `role="slider"`): Radix Slider does NOT propagate `aria-label` from the
 * Root container to the thumb, so a label left on the Root would leave the
 * slider nameless. This mirrors the documented Radix usage (set the label
 * on each Thumb) while keeping the consumer-facing `aria-label` API on the
 * wrapper (plan §Task 5).
 *
 * Presentation-only: callers pass resolved i18n labels (RULE-16). For the
 * adaptive-context preference-weight control use `max={1} step={0.01}`.
 * `className` and all other Radix props (incl. `ref` in React 19) are
 * forwarded to the Root.
 */
function Slider({
  className,
  "aria-label": ariaLabel,
  "aria-labelledby": ariaLabelledBy,
  ...props
}: React.ComponentProps<typeof SliderPrimitive.Root>) {
  return (
    <SliderPrimitive.Root
      className={cn("relative flex w-full touch-none select-none items-center", className)}
      {...props}
    >
      <SliderPrimitive.Track className="relative h-2 w-full grow overflow-hidden rounded-full bg-primary/20">
        <SliderPrimitive.Range className="absolute h-full bg-primary" />
      </SliderPrimitive.Track>
      <SliderPrimitive.Thumb
        className="block h-5 w-5 rounded-full border-2 border-primary bg-background ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50"
        {...(ariaLabel ? { "aria-label": ariaLabel } : {})}
        {...(ariaLabelledBy ? { "aria-labelledby": ariaLabelledBy } : {})}
      />
    </SliderPrimitive.Root>
  );
}

export { Slider };
