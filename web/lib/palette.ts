/**
 * The one way into the palette besides its key: the editor's slash door.
 *
 * A typed custom event, not a store: the palette's open state stays the one
 * `useState` in the shell (`web/routes/__root.tsx`), and this signal carries
 * no state of its own — it fires, the shell's listener opens with the
 * query, and there is nothing to snapshot, subscribe, or drift. A store
 * would duplicate `paletteOpen` (or add snapshot churn for a fire-and-forget
 * ask); the event funnels through the shell's one refusal — a live dialog
 * owns the stage — like ⌘K and the bar's chip already do.
 */

/** The window event the editor dispatches and the shell listens for. */
export const PALETTE_OPEN_EVENT = "narrare:open-palette" as const;

/** What the ask carries: the query the palette opens prefilled with. */
export type PaletteOpenDetail = {
  query: string;
};

/** Ask the shell to open the palette prefilled with `query`. */
export function requestPaletteOpen(query: string): void {
  window.dispatchEvent(
    new CustomEvent<PaletteOpenDetail>(PALETTE_OPEN_EVENT, { detail: { query } }),
  );
}
