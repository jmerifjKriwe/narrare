import type { ReactNode } from "react";

/**
 * The surface that holds a working set: a card-level box — the surface
 * radius, an edge of `--border` — with an optional labelled header riding
 * a `--rule` separator. Panels hold rows, tables and forms; never another
 * panel, and never a card inside the card (L5).
 */

const PANEL_CLASSES =
  "rounded-[var(--radius-lg)] border border-border bg-card";

const HEADER_CLASSES =
  "flex items-center justify-between gap-2 border-b border-rule px-3 py-2";

/** The panel's label: small, spaced capitals on the `--rule` separator. */
const TITLE_CLASSES = "text-label uppercase tracking-[0.1em] text-muted";

export function Panel({
  title,
  actions,
  dense = false,
  className,
  children,
}: {
  title?: ReactNode;
  /** Controls for the whole panel, at the header's far edge. */
  actions?: ReactNode;
  /** Tighter body padding, for panels that are a list of rows. */
  dense?: boolean;
  /**
   * Appended after the panel's own classes: the panel classes are the
   * contract, this the extension (the P3 precedence).
   */
  className?: string;
  children: ReactNode;
}) {
  return (
    <section
      className={
        className ? `${PANEL_CLASSES} ${className}` : PANEL_CLASSES
      }
    >
      {title || actions ? (
        <header className={HEADER_CLASSES}>
          {title ? <h2 className={TITLE_CLASSES}>{title}</h2> : null}
          {actions}
        </header>
      ) : null}
      <div className={dense ? "p-2" : "p-3"}>{children}</div>
    </section>
  );
}
