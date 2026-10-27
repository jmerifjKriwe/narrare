/**
 * The button paints the knowledge surfaces share: the primary action, the
 * quiet second choice, and the one a confirm dialog owes its danger to.
 * The tokens do the painting; the focus ring is the keyboard contract's.
 */
export const PRIMARY_BUTTON =
  "rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";
export const QUIET_BUTTON =
  "rounded-md border border-border px-3 py-2 text-sm font-medium hover:bg-panel focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";
export const DANGER_BUTTON =
  "rounded-md border border-danger px-3 py-2 text-sm font-medium text-danger hover:bg-panel focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";
