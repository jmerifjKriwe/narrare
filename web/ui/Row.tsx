import type { MouseEventHandler, ReactNode } from "react";

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
 */

/**
 * The row's constant classes: the control height, the layout, the body
 * type, the `--rule` separator (a row is separated, never edged —
 * `--border` is for surfaces) and the one focus ring every interactive
 * primitive carries.
 */
const ROW_CLASSES =
  "h-7 flex items-center gap-2 px-3 text-body border-b border-rule focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

/** The selected row's additions: the wash, the weight, the edge marker. */
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

export type RowProps = {
  /** The element to render. `href` wins over it: a destination is an anchor's job, so a `href` renders `<a>` whatever `as` says. */
  as?: "button" | "a" | "div";
  selected?: boolean;
  /**
   * `aria-current="true"` — the navigation's "you are here". It comes only
   * from this prop, never from `selected`: where you are and what you have
   * chosen are different facts, and screen readers announce them
   * differently (the L2 ruling).
   */
  current?: boolean;
  /** A glyph or badge before the row's content. */
  leading?: ReactNode;
  /** Something after the content — a status, a count, a control. */
  trailing?: ReactNode;
  href?: string;
  onClick?: MouseEventHandler<HTMLElement>;
  /**
   * Appended after the matrix: `rowClass` is the contract, this the
   * extension (the P3 precedence). A utility that fights the matrix here
   * is a smell — extend `rowClass` instead.
   */
  className?: string;
  children: ReactNode;
};

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
}: RowProps) {
  const classes = className
    ? `${rowClass(selected)} ${className}`
    : rowClass(selected);
  const inner = (
    <>
      {leading}
      {children}
      {trailing}
    </>
  );
  const state = {
    "data-selected": selected || undefined,
    "aria-current": current ? ("true" as const) : undefined,
    className: classes,
    onClick,
  };
  if (href) {
    return (
      <a href={href} {...state}>
        {inner}
      </a>
    );
  }
  if (as === "div") {
    // A div row carries no keyboard contract of its own — interaction
    // lives in the controls inside it (rows with buttons take this form;
    // a button inside a button is invalid HTML).
    return <div {...state}>{inner}</div>;
  }
  // `type: "button"`: a row that submits a form it never joined is a bug
  // waiting for a form (the Button rule, kept here).
  return (
    <button type="button" {...state}>
      {inner}
    </button>
  );
}
