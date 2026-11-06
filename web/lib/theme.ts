/**
 * The reader's light, and where the choice came from.
 *
 * Three sources, in this order: the user's stored choice (the server row), the
 * system's `prefers-color-scheme`, the light default. The row is the record; a
 * small `localStorage` mirror exists only so the first paint can know the
 * choice before the settings query answers — a cache, never a source, written
 * and overwritten by `applyTheme` alone.
 *
 * Nothing here talks to the API: the shell's boot calls `adoptServerTheme`, the
 * appearance page persists its own answer.
 */

export type Theme = "light" | "dark";

/** The mirror's key. `index.html` reads it before the module script; keep the
 *  two literals in step — the inline script cannot import this file. */
export const THEME_HINT = "narrare.theme";

/** Set or clear the document's theme and the pre-paint hint. */
export function applyTheme(theme: Theme | null): void {
  if (theme === null) {
    document.documentElement.removeAttribute("data-theme");
  } else {
    document.documentElement.dataset.theme = theme;
  }
  try {
    if (theme === null) localStorage.removeItem(THEME_HINT);
    else localStorage.setItem(THEME_HINT, theme);
  } catch {
    /* A blocked store costs the hint, never the choice: the row still holds it. */
  }
}

/** The boot's answer: the server row decides, anything unknown means "system". */
export function adoptServerTheme(theme: string | null): void {
  applyTheme(theme === "light" || theme === "dark" ? theme : null);
}
