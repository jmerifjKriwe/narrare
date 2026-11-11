import type { ButtonHTMLAttributes, ReactNode } from "react";

/**
 * The button primitive and its state matrix. One definition here: every
 * hover, focus and disabled look the product shows rides `buttonClass`, so
 * a variant cannot drift from its siblings. Behaviour (the real focus
 * ring, the axe pass) is pinned by the E2E suites; the class contract
 * itself is `buttonClasses.test.ts`.
 *
 * The matrix is the drafted ladder (spec §6.5): three heights — 28 px, the
 * dense floor, 36 px and 40 px — on the control radius, with the amber
 * focus ring and its 1 px offset on every cell. A size also chooses the
 * type step that rides it, as it always has.
 */

/** The five paints a button wears. */
export const BUTTON_VARIANTS = [
  "primary",
  "secondary",
  "ghost",
  "destructive",
  "icon",
] as const;
export type ButtonVariant = (typeof BUTTON_VARIANTS)[number];

/** The three heights of the drafted ladder: the dense floor, the middle, the large. */
export const BUTTON_SIZES = ["sm", "md", "lg"] as const;
export type ButtonSize = (typeof BUTTON_SIZES)[number];

/**
 * The radius a control wears: the 8 px control radius for the four
 * labelled paints, the 4 px small-control radius for the icon button.
 */
const CONTROL_RADIUS = "rounded-[var(--radius-control)]";
const ICON_RADIUS = "rounded-[var(--radius-sm)]";

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: `bg-primary text-primary-foreground shadow-sm hover:opacity-95 active:opacity-90 ${CONTROL_RADIUS}`,
  secondary: `border border-border bg-card hover:bg-soft ${CONTROL_RADIUS}`,
  // Hover's --soft fill drops muted text below AA (4.43:1 light), so the hover restores foreground.
  ghost: `text-muted hover:bg-soft hover:text-foreground ${CONTROL_RADIUS}`,
  // The destructive paint: outlined in the diagnostic colour, a tenth of it
  // on the hover. Border and ink only — the ground stays the card's.
  destructive: `border border-danger text-danger hover:bg-danger/10 ${CONTROL_RADIUS}`,
  // Icon strokes are non-text (3:1 rule): muted on --soft clears that, so no foreground swap here.
  // The glyph's own cell: 16 px glyph plus 6 px of padding, on the small radius.
  icon: `grid place-items-center text-muted hover:bg-soft ${ICON_RADIUS} p-1.5`,
};

// The focus ring and its 1 px gap. The offset's colour is Tailwind's white
// by default, which on the dark theme draws a white seam around the amber
// ring instead of a gap in the surface — so the offset is transparent and
// the surface shows through it.
const SHARED_CLASSES =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1 focus-visible:ring-offset-transparent disabled:opacity-50";

/** The height and the type step each size rides. */
const SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: "h-7 text-label",
  md: "h-9 text-body",
  lg: "h-10 text-emph",
};

/**
 * The horizontal inset the labelled controls wear. The icon button has
 * none: its cell is the glyph and the padding around it.
 */
const SIZE_INSET_CLASSES: Record<ButtonSize, string> = {
  sm: "px-2.5",
  md: "px-3",
  lg: "px-4",
};

/**
 * The whole matrix for one variant and size. Exported for the rare surface
 * that styles a non-button control with the button's states — not for
 * hand-rolling a variant.
 */
export function buttonClass(variant: ButtonVariant, size: ButtonSize): string {
  const classes = [VARIANT_CLASSES[variant], SHARED_CLASSES, SIZE_CLASSES[size]];
  if (variant !== "icon") classes.push(SIZE_INSET_CLASSES[size]);
  return classes.join(" ");
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
  size = "sm",  icon,
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
