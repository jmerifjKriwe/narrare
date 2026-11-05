import type { ReactNode } from "react";

/**
 * The surface that holds a working set: a card-level box — the surface
 * radius, an edge of `--border` — with an optional labelled header riding
 * a `--rule` separator. Panels hold rows, tables and forms; never another
 * panel, and never a card inside the card (L5).
 */

const PANEL_CLASSES =
  "rounded-[var(--radius-lg)] border border-border bg-card";

/** The panel's label: small, spaced capitals on the `--rule` separator. */
const TITLE_CLASSES = "text-label uppercase tracking-[0.1em] text-muted";

/**
 * The panel's content measure — the one knob `dense` turns. §8.3: a dense
 * panel keeps a 10 px measure, a regular one 12 px.
 */
export function panelClass(dense = false): string {
  return dense ? "p-2.5" : "p-3";
}

/** The header row: its label and actions on the `--rule` separator. */
export function panelHeaderClass(): string {
  return "flex items-center gap-2 border-b border-rule px-3 py-2";
}

export function Panel({
  title,
  actions,
  dense = false,
  titleAs = "h2",
  className,
  children,
}: {
  title?: ReactNode;
  /** Controls for the whole panel, at the header's far edge. */
  actions?: ReactNode;
  /** Tighter body padding, for panels that are a list of rows. */
  dense?: boolean;
  /** The heading level of the title — drop it a step when the panel nests. */
  titleAs?: "h2" | "h3" | "h4";
  /**
   * Appended after the panel's own classes: the panel classes are the
   * contract, this the extension (the P3 precedence).
   */
  className?: string;
  children: ReactNode;
}) {
  const Heading = titleAs;
  return (
    <section
      className={
        className ? `${PANEL_CLASSES} ${className}` : PANEL_CLASSES
      }
    >
      {title != null || actions != null ? (
        <header className={panelHeaderClass()}>
          {title != null ? (
            <Heading className={TITLE_CLASSES}>{title}</Heading>
          ) : null}
          {actions != null ? (
            <div className="ml-auto flex items-center gap-2">{actions}</div>
          ) : null}
        </header>
      ) : null}
      <div className={panelClass(dense)}>{children}</div>
    </section>
  );
}
