import type { HTMLAttributes, MouseEventHandler, ReactNode } from "react";

/**
 * The list row and its state string. One definition here: the plain `Row`
 * and the React-Aria `GridList.Item` consumers (the entity list, P13) wear
 * the same `rowClass`, so a row cannot drift from its siblings. The row is
 * a plain element — the keyboard contract of a selectable list stays with
 * React Aria, which is why nothing here renders roles.
 *
 * Selection is the L2 contract, not the filled block it replaces: the
 * `--soft` wash, weight 600 and a 2 px `--primary` edge at the row's
 * start. Text stays foreground — muted on the wash is below AA (4.43:1
 * light), and `bg-primary` fills are for the one primary action, never a
 * chosen row.
 *
 * Rows fill their container and read left (`w-full text-left`): a list of
 * them is a column, not a run of shrink-wrapped centred buttons.
 */

/**
 * The row's constant classes: the control height, the full-width layout,
 * the body type, the `--rule` separator (a row is separated, never edged —
 * `--border` is for surfaces), the pointer's wash and the one focus ring
 * every interactive primitive carries.
 */
const ROW_CLASSES =
  "h-7 flex w-full items-center gap-2 px-3 text-left text-body border-b border-rule hover:bg-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

/**
 * The selected row's additions: the weight and the edge marker — plus the
 * wash named again, because a selected row must wear it un-hovered too
 * (the hover only shares it).
 */
const ROW_SELECTED_CLASSES =
  "bg-soft font-semibold shadow-[inset_2px_0_0_var(--primary)]";

/**
 * The whole row look for one boolean. Exported so React Aria
 * `GridList.Item` consumers pass the selection they already hold —
 * `rowClass(item.id === selectedId)` — and rows in a React-Aria list wear
 * exactly what a plain `Row` wears.
 */
export function rowClass(selected: boolean): string {
  return selected ? `${ROW_CLASSES} ${ROW_SELECTED_CLASSES}` : ROW_CLASSES;
}

/**
 * The row's props. Everything an element takes rides through to the root
 * (the `Button` precedent) — P12's roving `tabIndex`/`onKeyDown` lands
 * there. The element is a discriminated union: an acting row is a button,
 * or an anchor when it carries an `href`; a `div` row is purely
 * presentational and takes neither `onClick` nor `href` — a clickable div
 * has no keyboard contract, so interaction lives in the controls inside it.
 */
type RowBase = Omit<HTMLAttributes<HTMLElement>, "onClick"> & {
  selected?: boolean;
  current?: boolean;
  /** A glyph or badge before the row's content. */
  leading?: ReactNode;
  /** Something after the content — a status, a count, a control. */
  trailing?: ReactNode;
};

export type RowProps =
  | (RowBase & {
      as?: "button" | "a";
      href?: string;
      onClick?: MouseEventHandler<HTMLElement>;
    })
  | (RowBase & { as: "div"; href?: never; onClick?: never });

export function Row({
  as = "button",
  selected = false,
  current = false,
  leading,
  trailing,
  href,
  onClick,
  className,
  children,
  ...rest
}: RowProps) {
  // Appended after the matrix: `rowClass` is the contract, this the
  // extension (the P3 precedence). A utility that fights the matrix here
  // is a smell — extend `rowClass` instead.
  const classes = className
    ? `${rowClass(selected)} ${className}`
    : rowClass(selected);
  const state = {
    "data-selected": selected || undefined,
    // `aria-current` is the navigation's "you are here"; it comes only
    // from `current`, never from `selected`: where you are and what you
    // have chosen are different facts (the L2 ruling).
    "aria-current": current ? ("true" as const) : undefined,
    className: classes,
  };
  const inner = (
    <>
      {leading}
      {children}
      {trailing}
    </>
  );
  if (as === "div") {
    // Purely presentational: no keyboard contract of its own. Rows with
    // buttons take this form — a button inside a button is invalid HTML.
    return (
      <div {...state} {...rest}>
        {inner}
      </div>
    );
  }
  // `href` wins over `as`: a destination is an anchor's job, so an href
  // renders `<a>` even when `as` says button.
  if (href || as === "a") {
    return (
      <a href={href} onClick={onClick} {...state} {...rest}>
        {inner}
      </a>
    );
  }
  // `type: "button"`: a row that submits a form it never joined is a bug
  // waiting for a form (the Button rule, kept here).
  return (
    <button type="button" onClick={onClick} {...state} {...rest}>
      {inner}
    </button>
  );
}
