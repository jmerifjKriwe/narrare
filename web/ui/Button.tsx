import type { ButtonHTMLAttributes, ReactNode } from "react";

/**
 * The button primitive and its state matrix. One definition here: every
 * hover, focus and disabled look the product shows rides `buttonClass`, so
 * a variant cannot drift from its siblings. Behaviour (the real focus
 * ring, the axe pass) is pinned by the E2E suites; the class contract
 * itself is `buttonClasses.test.ts`.
 */

/** The four paints a button wears. */
export const BUTTON_VARIANTS = [
  "primary",
  "secondary",
  "ghost",
  "icon",
] as const;
export type ButtonVariant = (typeof BUTTON_VARIANTS)[number];

/** The two control heights the type scale carries: sm = 24px, md = 28px. */
export const BUTTON_SIZES = ["sm", "md"] as const;
export type ButtonSize = (typeof BUTTON_SIZES)[number];

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary:
    "bg-primary text-primary-foreground hover:brightness-95 active:brightness-90",
  secondary: "border border-border bg-card hover:bg-soft",
  // Hover's --soft fill drops muted text below AA (4.43:1 light), so the hover restores foreground.
  ghost: "text-muted hover:bg-soft hover:text-foreground",
  // Icon strokes are non-text (3:1 rule): muted on --soft clears that, so no foreground swap here.
  icon: "grid place-items-center text-muted hover:bg-soft",
};

const SHARED_CLASSES =
  "rounded-[var(--radius)] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50";

const SIZE_CLASSES: Record<ButtonSize, string> = {
  md: "h-7 px-2.5 text-body",
  sm: "h-6 px-2 text-label",
};

/**
 * The whole matrix for one variant and size. Exported for the rare surface
 * that styles a non-button control with the button's states — not for
 * hand-rolling a variant.
 */
export function buttonClass(variant: ButtonVariant, size: ButtonSize): string {
  return `${VARIANT_CLASSES[variant]} ${SHARED_CLASSES} ${SIZE_CLASSES[size]}`;
}

/**
 * `variant: "icon"` demands `label` — an icon-only button with no
 * accessible name is unnamed to a screen reader; `title` alone is not
 * enough, and the glyph itself is optional (any content names it). The
 * `label` becomes the `aria-label` only when the button has no children —
 * applying it beside visible children would give the button an accessible
 * name that differs from its words. `type` defaults to `"button"`: a
 * control that submits a form it never joined is a bug waiting for a form.
 * Everything else a `<button>` takes rides through unchanged.
 */
export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  size?: ButtonSize;
} & (
    | { variant: "icon"; icon?: ReactNode; label: string }
    | {
        variant?: Exclude<ButtonVariant, "icon">;
        icon?: ReactNode;
        label?: string;
      }
  );

export function Button({
  variant = "secondary",
  size = "md",
  icon,
  label,
  type = "button",
  disabled = false,
  onClick,
  className,
  children,
  ...rest
}: ButtonProps) {
  const classes = className
    ? `${buttonClass(variant, size)} ${className}`
    : buttonClass(variant, size);
  // An icon beside a label needs a gap and a line box of its own: the glyph
  // is a 16 px SVG, and inline-block flow would sit it on the text's
  // baseline without air. Icon-only buttons are the `icon` variant's grid.
  const withIcon = icon != null && children != null ? "inline-flex items-center gap-1.5" : "";
  return (
    <button
      // Set ahead of the spread so a caller's own aria-label still wins.
      aria-label={children ? undefined : label}
      {...rest}
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={withIcon ? `${classes} ${withIcon}` : classes}
    >
      {icon}
      {children}
    </button>
  );
}
