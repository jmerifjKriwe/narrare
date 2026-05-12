"use client";

import { Button as ButtonPrimitive } from "@base-ui/react/button";
import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef } from "react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center rounded-lg border border-transparent bg-clip-padding font-medium whitespace-nowrap transition-all outline-none select-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 active:not-aria-[haspopup]:translate-y-px disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        primary: "bg-primary text-primary-foreground hover:bg-primary/90",
        secondary: "bg-secondary text-secondary-foreground border-border hover:bg-secondary/80",
        ghost: "hover:bg-muted hover:text-foreground",
        danger: "bg-destructive text-white hover:bg-destructive/90",
      },
      size: {
        sm: "h-7 gap-1 px-3 text-[0.8125rem]",
        md: "h-9 gap-1.5 px-4 text-[0.9375rem]",
        lg: "h-10 gap-1.5 px-6 text-base",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  },
);

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: VariantProps<typeof buttonVariants>["variant"];
  size?: VariantProps<typeof buttonVariants>["size"];
  loading?: boolean;
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, loading, children, disabled, ...props }, ref) => {
    return (
      <ButtonPrimitive
        ref={ref}
        data-slot="button"
        disabled={disabled || loading}
        className={cn(buttonVariants({ variant, size, className }))}
        {...props}
      >
        {loading && (
          <span
            className="h-[1em] w-[1em] animate-spin rounded-full border-2 border-white/30 border-t-white"
            aria-hidden="true"
          />
        )}
        <span className={loading ? "opacity-70" : undefined}>{children}</span>
      </ButtonPrimitive>
    );
  },
);
Button.displayName = "Button";

export type { ButtonProps };
export { Button, buttonVariants };
