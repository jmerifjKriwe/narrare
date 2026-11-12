import type { ReactNode } from "react";

/**
 * The drafted keycap badge (spec §6.5): a physical key, named as one
 * (`<kbd>` — the semantics a screen reader reads as "keyboard input"),
 * wearing the shell the drafts put on ⌘, K, Tab and Esc — the card's
 * ground behind a hairline edge, the 4 px small-control radius, the meta
 * step in the muted ink. A keycap is a hint, never a control: it carries
 * no elevation and no pointer state of its own, because the border
 * discipline keeps decorative box-shadow off anything that is not a
 * tier. The interactive shell around one — the bar's palette chip, the
 * ghost-text trailer — is the caller's; this is the glyph's ground, one
 * definition for every key the app names.
 */

/** The keycap's shell: one string, worn by every key the app names. */
const KEYCAP_CLASSES =
  "inline-flex items-center rounded-[var(--radius-sm)] border border-border bg-card px-1.5 py-0.5 text-meta leading-none text-muted";

export function Keycap({ children }: { children: ReactNode }) {
  return <kbd className={KEYCAP_CLASSES}>{children}</kbd>;
}
