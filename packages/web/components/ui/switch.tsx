"use client";

import * as SwitchPrimitive from "@radix-ui/react-switch";
import type * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Accessible toggle switch built on Radix Switch.
 *
 * Renders a `role="switch"` button that is keyboard-operable (Space to
 * toggle, focusable via Tab) and exposes `aria-checked` automatically from
 * Radix. Pass an `aria-label` so screen readers announce its purpose
 * (ui-principles §11).
 *
 * The unchecked track uses the design-system `bg-switch-background` token
 * — NOT shadcn's default `bg-input`, which is `transparent` in the Narrare
 * theme and would render an invisible track (see themes/narrare.css §30).
 * Presentation-only: callers pass resolved i18n labels (RULE-16).
 */
function Switch({ className, ...props }: React.ComponentProps<typeof SwitchPrimitive.Root>) {
  return (
    <SwitchPrimitive.Root
      className={cn(
        "peer inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=unchecked]:bg-switch-background",
        className,
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb className="pointer-events-none block h-5 w-5 rounded-full bg-background shadow-lg ring-0 transition-transform data-[state=checked]:translate-x-4 data-[state=unchecked]:translate-x-0" />
    </SwitchPrimitive.Root>
  );
}

export { Switch };
