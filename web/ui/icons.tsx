import type { ReactNode } from "react";

/**
 * The icon set: sixteen line glyphs on one 16×16 grid, drawn for the
 * stroke they run on — `currentColor` at 1.5, round caps and joins, no
 * fills — so a glyph wears the ink of whatever it sits beside and carries
 * no color of its own. The whole presentation contract lives on the
 * `<svg>` that `Icon` renders, once; the entries of `icons` are the inner
 * drawings, bare geometry with no attributes of their own.
 *
 * The set replaces the app's only glyph, the `⚙` in the TopBar, with the
 * wave's whole vocabulary; P9 wires the names into the controls. A glyph
 * is never its own accessible name — `Icon` is always `aria-hidden`, and
 * the control's label (P7's catalog keys) does the naming.
 */

/**
 * The sixteen drawings. Each stays inside the 2.5–13.5 box so the 1.5
 * stroke never clips the viewBox, and each is a single-stroke metaphor:
 * detail that disappears at 16 px is detail left out.
 */
export const icons = {
  /** The library: an open book, its pages dipping to the spine. */
  books: (
    <path d="M8 4.6C6.6 3.7 4.6 3.4 2.5 3.7V12C4.6 11.7 6.6 12 8 13C9.4 12 11.4 11.7 13.5 12V3.7C11.4 3.4 9.4 3.7 8 4.6ZM8 4.6V13" />
  ),
  /** The editor: a pencil, tip to the page. */
  write: <path d="M10.9 3.1L12.9 5.1L5.4 12.6L2.5 13.5L3.4 10.6ZM3.4 10.6L5.4 12.6" />,
  /** The knowledge base: a stack, read top down. */
  knowledge: (
    <>
      <ellipse cx="8" cy="4.25" rx="5" ry="1.9" />
      <path d="M3 4.25V11.75M13 4.25V11.75M3 8A5 1.9 0 0 0 13 8M3 11.75A5 1.9 0 0 0 13 11.75" />
    </>
  ),
  /** Chat: a speech bubble with its tail. */
  chat: (
    <path d="M2.5 4A1.5 1.5 0 0 1 4 2.5H12A1.5 1.5 0 0 1 13.5 4V9A1.5 1.5 0 0 1 12 10.5H8L4.5 13.5V10.5H4A1.5 1.5 0 0 1 2.5 9Z" />
  ),
  /** Settings: a cog — the ⚙ it replaces, ring and teeth. */
  settings: (
    <>
      <circle cx="8" cy="8" r="2.5" />
      <path d="M8 4.5V2.75M8 11.5V13.25M4.5 8H2.75M11.5 8H13.25M5.53 5.53L4.29 4.29M10.47 5.53L11.71 4.29M5.53 10.47L4.29 11.71M10.47 10.47L11.71 11.71" />
    </>
  ),
  /** Distraction-free focus: the corners of the page alone. */
  focus: <path d="M5.5 2.5H2.5V5.5M10.5 2.5H13.5V5.5M13.5 10.5V13.5H10.5M5.5 13.5H2.5V10.5" />,
  /** Collapse the rail: the arrow leaves the content. */
  railHide: <path d="M2.5 2.5H13.5V13.5H2.5ZM5.5 2.5V13.5M11.5 8H7.5M9.5 6L7.5 8L9.5 10" />,
  /** Bring the rail back: the arrow returns. */
  railShow: <path d="M2.5 2.5H13.5V13.5H2.5ZM5.5 2.5V13.5M7.5 8H11.5M9.5 6L11.5 8L9.5 10" />,
  /** Panel gone: its header rule, the body folded down under it. */
  close: <path d="M3 4H13M5.5 7.2L8 9.7L10.5 7.2" />,
  /** Export: out of the tray, upward. */
  export: (
    <path d="M8 10V2.5M5.5 5L8 2.5L10.5 5M3 10.5V12A1.5 1.5 0 0 0 4.5 13.5H11.5A1.5 1.5 0 0 0 13 12V10.5" />
  ),
  /** Import: into the tray, downward. */
  import: (
    <path d="M8 2.5V10M5.5 7.5L8 10L10.5 7.5M3 10.5V12A1.5 1.5 0 0 0 4.5 13.5H11.5A1.5 1.5 0 0 0 13 12V10.5" />
  ),
  /** Search: the lens and its handle. */
  search: (
    <>
      <circle cx="7" cy="7" r="4.25" />
      <path d="M10.3 10.3L13.5 13.5" />
    </>
  ),
  /** Add: the plain plus. */
  plus: <path d="M8 3V13M3 8H13" />,
  /** Confirm: the plain check. */
  check: <path d="M3 8.5L6.5 12L13 4.5" />,
  /** Dismiss: the ✕. Not `close` — a dismissal drops content, a close folds a panel. */
  cross: <path d="M4.5 4.5L11.5 11.5M11.5 4.5L4.5 11.5" />,
  /** Disclosure: selects and menus point down. */
  chevronDown: <path d="M3.5 6L8 10.5L12.5 6" />,
} satisfies Record<string, ReactNode>;

/** A name in the icon set — the wave's whole glyph vocabulary. */
export type IconName = keyof typeof icons;

/**
 * One glyph at one size: the drawing stays on its 16×16 grid and the box
 * around it grows, so `size` never re-proportions a drawing. Always
 * `aria-hidden` — the accessible name belongs to the control that carries
 * the glyph, never to the picture.
 */
export function Icon({ name, size = 16 }: { name: IconName; size?: number }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {icons[name]}
    </svg>
  );
}
