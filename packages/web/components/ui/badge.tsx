import { cva, type VariantProps } from "class-variance-authority";
import type * as React from "react";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground hover:opacity-90",
        secondary: "border-transparent bg-secondary text-secondary-foreground hover:opacity-90",
        destructive:
          "border-transparent bg-destructive text-destructive-foreground hover:opacity-90",
        outline: "text-foreground border-border",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends React.ComponentProps<"div">,
    VariantProps<typeof badgeVariants> {}

/**
 * Compact status / category label — a non-interactive styled `<div>`.
 *
 * Consumed by adaptive-context UI (e.g. preference-tier badges: low / medium
 * / high) and other panels. Variants map to design-system tokens
 * (`bg-primary`, `bg-secondary`, `bg-destructive`, `border-border`).
 * Presentation-only.
 */
function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
