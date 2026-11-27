import type { ReactNode } from "react";

/**
 * The icon set: seventy line glyphs on one 16×16 grid, drawn for the
 * stroke they run on — `currentColor` at 1.5, round caps and joins, no
 * fills — so a glyph wears the ink of whatever it sits beside and carries
 * no color of its own. The whole presentation contract lives on the
 * `<svg>` that `Icon` renders, once; the entries of `icons` are the inner
 * drawings, bare geometry with no attributes of their own.
 *
 * The set replaces the app's only glyph, the `⚙` in the TopBar, with the
 * wave's whole vocabulary; P9 wired the names into the controls. A glyph
 * is never its own accessible name — `Icon` is always `aria-hidden`, and
 * the control's label (P7's catalog keys) does the naming.
 */

/**
 * The seventy drawings. Each stays inside the 2.35–13.65 envelope —
 * knowledge's stack sets both extremes; on the x axis the ink never leaves
 * 2.5–13.5 — so the 1.5 stroke, reaching half its width past the ink, never
 * clips the viewBox. Each is a single-stroke metaphor: detail that
 * disappears at 16 px is detail left out.
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
  /** Panel gone: its header rule, the body folded down under it. Centred
   * on (8, 8): the ink spans 5.15–10.85, so the glyph sits in its box
   * instead of floating 1.15 units above it (P6's finding). */
  close: <path d="M3 5.15H13M5.5 8.35L8 10.85L10.5 8.35" />,
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
  /** Remove: the plain minus — the plus's counterpart, the zoom-out's mark. */
  minus: <path d="M3 8H13" />,
  /** Confirm: the plain check. */
  check: <path d="M3 8.5L6.5 12L13 4.5" />,
  /** Dismiss: the ✕. Not `close` — a dismissal drops content, a close folds a panel. */
  cross: <path d="M4.5 4.5L11.5 11.5M11.5 4.5L4.5 11.5" />,
  /** Disclosure: selects and menus point down. */
  chevronDown: <path d="M3.5 6L8 10.5L12.5 6" />,
  /** The open menu's mark: the disclosure turned upward — the chrome's
   *  language chip wears it while its menu stands (the draft's expand_less). */
  expandLess: <path d="M3.5 10L8 5.5L12.5 10" />,
  /** The select's own caret: the disclosure mark, tightened for a control
   *  that has text beside it — a wide chevron crowds the value. */
  selectChevron: <path d="M4.5 6.5L8 10L11.5 6.5" />,
  /** The scene plan: the chapter's scenes in their order — a spine with
   *  one row per scene, the last row shorter, because a plan is a list
   *  that ends. The workspace's dock tabs name the registry's ids, so a
   *  new dock needs its glyph here (the tab's `Icon name={dock.id}`). */
  planning: <path d="M6 3.5V12.5M6 5.5H12.5M6 8H12.5M6 10.5H10" />,

  // The drafted concepts. Deviation #1 (spec §6.9): the drafts speak in
  // Material Symbols, the app keeps its own faces. A Material name pins
  // the *concept*; the drawing below is the app's own.

  /** The story the app writes for you: a closed volume with the spark
   *  beside it. Distinct from `books` — that one is the open library,
   *  this one a single title — and from `menuBook`, which is the
   *  manuscript opened at its contents. */
  autoStories: (
    <>
      <path d="M2.6 4.6H10.8V13.4H2.6Z" />
      <path d="M5 4.6V13.4" />
      <path d="M12.3 2.7L12.7 3.5L13.6 3.9L12.7 4.3L12.3 5.1L11.9 4.3L11 3.9L11.9 3.5Z" />
    </>
  ),
  /** A collection of saved works: two cards overlapping, a bookmark tab
   *  standing out of the back one. */
  bookmarkCollection: (
    <>
      <path d="M3.4 5.4H9V11.4H3.4Z" />
      <path d="M6.4 8.4H12V13.4H6.4Z" />
      <path d="M5.2 5.4V3.4H7.2V5.4" />
    </>
  ),
  /** A check inside a ring: the state is settled, not merely marked. */
  checkCircle: (
    <>
      <circle cx="8" cy="8" r="5.5" />
      <path d="M5.2 8.2L7.2 10.2L10.9 5.6" />
    </>
  ),
  /** A clock face, hands at ten past ten. */
  clock: (
    <>
      <circle cx="8" cy="8" r="5.5" />
      <path d="M8 4.6V8.2L10.6 9.6" />
    </>
  ),
  /** The quiet fact: the info card's mark — a circle around an i. */
  info: (
    <>
      <circle cx="8" cy="8" r="5.5" />
      <path d="M8 7.4V11M8 4.9V5" />
    </>
  ),
  /** The editor's note: ruled lines with the nib laid against them. */
  editNote: (
    <>
      <path d="M2.8 5.4H10.4M2.8 8.4H8.6M2.8 11.4H6.4" />
      <path d="M11.2 9.2L13.4 7L12.3 5.9L10.1 8.1Z" />
    </>
  ),
  /** Fog on the flat: a cloud with the ground under it. */
  foggy: (
    <>
      <path d="M4.4 10.2C3 10.2 2.9 7.8 4.3 7.2C4.3 4.8 6 3.2 8.2 3.6C10 3.9 11 5.5 10.8 6.6C12.2 7 12.7 8.8 11.8 9.8C11.4 10.1 10.8 10.2 10.3 10.2Z" />
      <path d="M2.8 13.4H13.2" />
    </>
  ),
  /** The language: a globe, its meridian and equator. */
  globe: (
    <>
      <circle cx="8" cy="8" r="5.5" />
      <ellipse cx="8" cy="8" rx="2.3" ry="5.5" />
      <path d="M2.5 8H13.5" />
    </>
  ),
  /** The grid: four cells of one shelf. */
  gridView: <path d="M3 3H7V7H3Z M9 3H13V7H9Z M3 9H7V13H3Z M9 9H13V13H9Z" />,
  /** The work's own past: a ring running backwards, its arrowhead
   *  pointing the way the ring came. */
  historyEdu: (
    <>
      <path d="M4.17 4.79A5 5 0 1 0 10.5 3.67" />
      <path d="M10.5 3.67L12.3 3.55M10.5 3.67L11.3 5.29" />
    </>
  ),
  /** A house: the cottage the drafts draw on a cover. */
  house: (
    <>
      <path d="M2.6 7.4L8 2.9L13.4 7.4" />
      <path d="M4.6 6.4V13.2H11.4V6.4" />
    </>
  ),
  /** The relation net: three nodes wired to each other. */
  hub: (
    <>
      <circle cx="4" cy="4" r="1.5" />
      <circle cx="12" cy="4" r="1.5" />
      <circle cx="8" cy="12" r="1.5" />
      <path d="M5.5 4H10.5M11 5.2L8.9 10.8M5 5.2L7.1 10.8" />
    </>
  ),
  /** The highlighter: a broad nib laid down on the line it marks. */
  inkHighlighter: (
    <>
      <path d="M9.2 3.2L12.4 6.4L6.6 12.2H3.4L4.6 10.4Z" />
      <path d="M2.6 12.2H13.4" />
    </>
  ),
  /** The insight: a trend line climbing to the right. */
  insights: (
    <>
      <path d="M2.6 11.6L6.2 7.8L9.2 9.8L13.4 5" />
      <path d="M10.4 4.8H13.6V8" />
    </>
  ),
  /** The streak: a flame. */
  localFire: (
    <>
      <path d="M8 2.4C8 5.2 4.8 6.6 4.8 9.6C4.8 11.8 6.2 13.6 8 13.6C9.8 13.6 11.2 11.8 11.2 9.6C11.2 6.6 8 5.2 8 2.4Z" />
      <path d="M8 7.4C8 9.2 6.6 9.8 6.6 11.2C6.6 12.2 7.2 13 8 13C8.8 13 9.4 12.2 9.4 11.2C9.4 9.8 8 9.2 8 7.4Z" />
    </>
  ),
  /** The manuscript: a book opened at its table of contents. */
  menuBook: (
    <>
      <path d="M3 4C4.8 2.9 6.4 2.9 7.8 4C9.2 2.9 10.8 2.9 12.6 4V11.4C10.8 10.3 9.2 10.3 7.8 11.4C6.4 10.3 4.8 10.3 3 11.4Z" />
      <path d="M9 6.6H11.2M9 9H11.2" />
    </>
  ),
  /** More: three dots in a row. */
  moreHoriz: (
    <>
      <circle cx="4" cy="8" r="1.05" />
      <circle cx="8" cy="8" r="1.05" />
      <circle cx="12" cy="8" r="1.05" />
    </>
  ),
  /** More, stacked: three dots in a column — the quick menu's trigger
   *  (the draft's `more_vert`), distinct from the row's `moreHoriz`. */
  moreVert: (
    <>
      <circle cx="8" cy="4" r="1.05" />
      <circle cx="8" cy="8" r="1.05" />
      <circle cx="8" cy="12" r="1.05" />
    </>
  ),
  /** A person: the head over the shoulders. */
  person: (
    <>
      <circle cx="8" cy="5.4" r="2.2" />
      <path d="M3.4 13.4C3.4 10.6 5.4 8.8 8 8.8C10.6 8.8 12.6 10.6 12.6 13.4" />
    </>
  ),
  /** The radar: a sweep from a point, its echo bending away. */
  radar: (
    <>
      <circle cx="4" cy="12" r="1" />
      <path d="M4 8.4C4.63 8.4 5.25 8.57 5.8 8.88C6.35 9.2 6.8 9.65 7.12 10.2C7.43 10.75 7.6 11.37 7.6 12" />
      <path d="M4 5.6C5.12 5.6 6.23 5.9 7.2 6.46C8.17 7.02 8.98 7.83 9.54 8.8C10.1 9.77 10.4 10.88 10.4 12" />
    </>
  ),
  /** The schema: a table of fields, its header ruled off. */
  schema: (
    <>
      <path d="M2.6 3.6H13.4V12.4H2.6Z" />
      <path d="M2.6 6.6H13.4" />
      <path d="M8 6.6V12.4" />
    </>
  ),
  /** The theme: a moon, its dark side cut away. The outer edge is one
   *  arc of a circle whose centre the box can bound; the cut is a curve,
   *  so the crescent's horns sit at the arc's ends. */
  theme: (
    <path d="M10.35 3.41A5.3 5.3 0 1 0 10.35 12.59C7.6 12 6.4 10.2 6.4 8C6.4 5.8 7.6 4 10.35 3.41Z" />
  ),
  /** The tuning: two sliders, each knob on its own track. */
  tune: (
    <>
      <path d="M2.6 5.4H13.4M2.6 10.6H13.4" />
      <circle cx="5.4" cy="5.4" r="1.6" />
      <circle cx="10.4" cy="10.6" r="1.6" />
    </>
  ),
  /** The list: a row of entries, each with its bullet. */
  viewList: (
    <>
      <circle cx="3.4" cy="4.6" r="0.95" />
      <circle cx="3.4" cy="8" r="0.95" />
      <circle cx="3.4" cy="11.4" r="0.95" />
      <path d="M6 4.6H13.4M6 8H13.4M6 11.4H13.4" />
    </>
  ),
  /** Waves: three rolls of water, one over the next. */
  waves: (
    <>
      <path d="M2.6 4.6C3.8 3.4 5 5.8 6.2 4.6C7.4 3.4 8.6 5.8 9.8 4.6C11 3.4 12.2 5.8 13.4 4.6" />
      <path d="M2.6 8C3.8 6.8 5 9.2 6.2 8C7.4 6.8 8.6 9.2 9.8 8C11 6.8 12.2 9.2 13.4 8" />
      <path d="M2.6 11.4C3.8 10.2 5 12.6 6.2 11.4C7.4 10.2 8.6 12.6 9.8 11.4C11 10.2 12.2 12.6 13.4 11.4" />
    </>
  ),

  // The quick menu's concepts (shelf-quick-menu). Same rule as above: a
  // Material name pins the concept, the drawing is the app's own face.

  /** The drafts' `content_copy`: a second sheet lifted off the first —
   *  the duplicate that leaves the original whole. */
  copy: (
    <>
      <path d="M2.75 5.5H10.5V13.25H2.75Z" />
      <path d="M5.5 5.5V2.75H13.25V10.5H10.5" />
    </>
  ),
  /** The drafts' `inventory_2`: a lidded box with a hand slot — the
   *  archive that keeps the work, never a grave. */
  archive: (
    <>
      <path d="M2.75 3.25H13.25V5.75H2.75Z" />
      <path d="M3.75 5.75V12.75H12.25V5.75" />
      <path d="M6.5 8.5H9.5" />
    </>
  ),
  /** The drafts' `unarchive`: the same box, its arrow rising out — the
   *  symmetric return to the shelf. */
  unarchive: (
    <>
      <path d="M2.75 3.25H13.25V5.75H2.75Z" />
      <path d="M3.75 5.75V12.75H12.25V5.75" />
      <path d="M8 11.25V7.75M6.25 9.5L8 7.75L9.75 9.5" />
    </>
  ),

  // The welcome screen's concepts (welcome-atelier). Same rule as above: a
  // Material name pins the concept, the drawing is the app's own face.

  /** The way forward: a shaft and its head, pointing east. The drafts'
   *  `arrow_forward` and `east` are one concept — the step that follows. */
  arrowRight: <path d="M2.75 8H13.25M9.5 4.25L13.25 8L9.5 11.75" />,
  /** A manuscript brought in: a leaf with its folded corner and an arrow
   *  rising into it. The drafts' `upload_file`. */
  uploadFile: (
    <>
      <path d="M4 2.75H9.5L12 5.25V13.25H4Z" />
      <path d="M9.5 2.75V5.25H12" />
      <path d="M8 11V7.25M6.25 9L8 7.25L9.75 9" />
    </>
  ),
  /** The drafts' `cloud_upload`: the foggy cloud, its floor opened, an
   *  arrow climbing into it from below. */
  cloudUpload: (
    <>
      <path d="M4.4 10.2C3 10.2 2.9 7.8 4.3 7.2C4.3 4.8 6 3.2 8.2 3.6C10 3.9 11 5.5 10.8 6.6C12.2 7 12.7 8.8 11.8 9.8C11.4 10.1 10.8 10.2 10.3 10.2" />
      <path d="M8 13.4V8.6M6.25 10.35L8 8.6L9.75 10.35" />
    </>
  ),
  /** The drafts' `description`: a leaf with its folded corner and two
   *  ruled lines — a document, distinct from `uploadFile`'s rising arrow. */
  document: (
    <>
      <path d="M4 2.75H9.5L12 5.25V13.25H4Z" />
      <path d="M9.5 2.75V5.25H12" />
      <path d="M6 8.25H10M6 10.75H10" />
    </>
  ),
  /** The drafts' `lock`: a shackle over a body, its keyhole a single stroke. */
  lock: (
    <>
      <path d="M4.25 7.25H11.75V13.25H4.25Z" />
      <path d="M5.75 7.25V5.25A2.3 2.3 0 0 1 10.25 5.25V7.25" />
      <path d="M8 9.5V11" />
    </>
  ),
  /** The drafts' `balance`: a beam on a pillar, two pans hung from its
   *  ends — the causality guardian's scales. */
  balance: (
    <>
      <path d="M8 3V13.25" />
      <path d="M5.5 13.25H10.5" />
      <path d="M3.75 5H12.25" />
      <path d="M3.75 5L2.55 8.5M3.75 5L4.95 8.5" />
      <path d="M2.55 8.5A1.25 1.25 0 0 0 4.95 8.5" />
      <path d="M12.25 5L11.05 8.5M12.25 5L13.45 8.5" />
      <path d="M11.05 8.5A1.25 1.25 0 0 0 13.45 8.5" />
    </>
  ),
  /** The drafts' `shield`: a guard's badge, point down. */
  shield: (
    <path d="M8 2.75L12.75 4.5V8.5C12.75 11 10.75 12.75 8 13.4C5.25 12.75 3.25 11 3.25 8.5V4.5Z" />
  ),
  /** The drafts' `open_in_new`: a frame opened at its top-right corner,
   *  an arrow leaving through it. */
  openInNew: (
    <>
      <path d="M9.5 2.75H13.25V6.5" />
      <path d="M13.25 2.75L7.75 8.25" />
      <path d="M11 9.75V13.25H2.75V5H6.25" />
    </>
  ),

  // The provisioning step's concepts (setup-step4-bereitstellung-start,
  // setup-states-reference panels 3–4). Same rule as above: a Material
  // name pins the concept, the drawing is the app's own face.

  /** The drafts' `report_problem`: a warning triangle, its bang a stroke
   *  and a point — the failure card's calm alarm, never a panic face. */
  warning: (
    <>
      <path d="M8 2.9L13.4 12.5H2.6Z" />
      <path d="M8 6.5V9.5" />
      <circle cx="8" cy="11.3" r="0.4" />
    </>
  ),
  /** The drafts' `refresh`: a ring running clockwise, its arrowhead at
   *  the top — the retry that asks again. Distinct from `historyEdu`,
   *  whose ring runs backwards into the work's own past. */
  refresh: (
    <>
      <path d="M12.3 8A4.3 4.3 0 1 1 10.9 4.9" />
      <path d="M10.9 2.9V4.9H12.9" />
    </>
  ),

  // The app-wide chrome's concepts (chrome-rail-topbar, W4). Same rule as
  // above: a Material name pins the concept, the drawing is the app's own.

  /** The drafts' `unfold_more`: the two chevrons facing apart — the book
   *  switcher's mark, a choice that opens both ways. */
  unfoldMore: <path d="M4.5 6.5L8 3.5L11.5 6.5M4.5 9.5L8 12.5L11.5 9.5" />,

  // The workspace tree's concepts (workspace-scene-centric, W4 Task 13).
  // Same rule as above: a Material name pins the concept, the drawing is
  // the app's own face.

  /** The drafts' `drag_indicator`: six dots in two columns — the grip that
   *  moves a row, the tree's reorder at both levels. */
  dragIndicator: (
    <>
      <circle cx="6" cy="4" r="0.9" />
      <circle cx="10" cy="4" r="0.9" />
      <circle cx="6" cy="8" r="0.9" />
      <circle cx="10" cy="8" r="0.9" />
      <circle cx="6" cy="12" r="0.9" />
      <circle cx="10" cy="12" r="0.9" />
    </>
  ),
  /** The drafts' `delete`: a lidded bin with two ribs — the row's end,
   *  distinct from `archive`, which keeps the work. */
  trash: (
    <>
      <path d="M3.5 4.5H12.5" />
      <path d="M6.5 4.5V3.25H9.5V4.5" />
      <path d="M4.5 4.5L5.25 13H10.75L11.5 4.5" />
      <path d="M6.75 7V10.5M9.25 7V10.5" />
    </>
  ),

  // The continuation's concepts (workspace-scene-centric + workspace-states
  // KACHEL 7, W4 Task 16). Same rule as above: a Material name pins the
  // concept, the drawing is the app's own face.

  /** The drafts' `spark`: the four-pointed star — the prompt bar's primary
   *  action, the AI's own mark (the light face wins over the dark's ⌘K,
   *  which belongs to the disabled palette chip). */
  spark: <path d="M8 2.75L9.4 6.6L13.25 8L9.4 9.4L8 13.25L6.6 9.4L2.75 8L6.6 6.6Z" />,
  /** The drafts' `stop_circle`: a ring around a full square — the stream's
   *  abort, distinct from `cross`, which dismisses a face. */
  stopCircle: (
    <>
      <circle cx="8" cy="8" r="5.5" />
      <path d="M6.25 6.25H9.75V9.75H6.25Z" />
    </>
  ),
  /** The drafts' `arrow_back`: the zen exit chip's way home — the welcome
   *  screen's arrowRight, mirrored (W4 Task 18, zen-focus-2). */
  arrowLeft: <path d="M13.25 8H2.75M6.5 4.25L2.75 8L6.5 11.75" />,
  /** The drafts' `pause`: the pomodoro's held clock — two bars, no fill. */
  pause: <path d="M5.75 3.5V12.5M10.25 3.5V12.5" />,
  /** The drafts' `play_arrow`: the pomodoro's running clock — the triangle
   *  points the way the time flows. */
  play: <path d="M5.25 3.25L12 8L5.25 12.75Z" />,
  /** The drafts' `volume_off`: the muted soundscape — the speaker and the
   *  ✕ that silences it (the lock beside it is the set's own `lock`). */
  soundOff: (
    <>
      <path d="M2.5 6.25H4.75L8 3.5V12.5L4.75 9.75H2.5Z" />
      <path d="M10.5 6.25L13.5 9.75M13.5 6.25L10.5 9.75" />
    </>
  ),
  /** The drafts' `fullscreen`: the four corners pushed outward — the room
   *  grows to the screen's edge. */
  fullscreen: <path d="M2.75 5.5V2.75H5.5M10.5 2.75H13.25V5.5M13.25 10.5V13.25H10.5M5.5 13.25H2.75V10.5" />,
  /** The drafts' `fullscreen_exit`: the corners drawn back in — the screen
   *  returns to the window. */
  fullscreenExit: <path d="M5.5 2.75V5.5H2.75M10.5 2.75V5.5H13.25M13.25 10.5H10.5V13.25M2.75 10.5H5.5V13.25" />,

  // The keyboard's concepts (screenshot font determinism). The bundled mono
  // Latin subset carries no U+2318, and a system glyph is exactly the
  // machine-dependent ink the capture guard forbids — so the mark is drawn.

  /** The command key: the square and the four loops it hangs — the ⌘ the
   *  keycaps used to set as text. One closed path, as the glyph itself is. */
  command: (
    <path d="M9.875 4.25V11.75A1.875 1.875 0 1 0 11.75 9.875H4.25A1.875 1.875 0 1 0 6.125 11.75V4.25A1.875 1.875 0 1 0 4.25 6.125H11.75A1.875 1.875 0 1 0 9.875 4.25Z" />
  ),
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
