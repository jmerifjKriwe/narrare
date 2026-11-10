import { t, type MessageKey } from "./i18n";
import { isMac } from "./platform";

/**
 * Where a binding applies: everywhere, in the editor, or in the workspace
 * around it. The palette's own list walk (arrows, Enter) and plain control
 * activation (Enter/Space on a button, typing in a field) are standard
 * control behaviour, not shortcuts, so they stand outside this list.
 */
export type ShortcutScope = "global" | "editor" | "workspace";

export interface Shortcut {
  /** The stable id the pages and the tests address the binding by. */
  id: string;
  /** The catalog key naming the action, in every locale. */
  labelKey: MessageKey;
  /** The catalog key holding the Apple platform's keycap. */
  macKey: MessageKey;
  /** The catalog key holding every other platform's keycap. */
  otherKey: MessageKey;
  scope: ShortcutScope;
}

/**
 * The bindings the app really answers to — each verified against the
 * listener it names, no aspirational entries:
 *
 * - `palette.toggle`: the ⌘K/Ctrl+K listener beside the shell mount
 *   (`web/routes/__root.tsx`), opening and closing the palette.
 * - `workspace.focusDeeper` (F9) and `workspace.stepBack` (Esc): the
 *   window listener on the workbench (`NovelPage.tsx`) stepping the focus.
 * - `editor.acceptGhost` (Tab) and `editor.discardGhost` (Esc): the ghost's
 *   ProseMirror keys (`ghostText.ts`); a pending ghost's Esc never reaches
 *   the workbench, so discarding and stepping back are two bindings.
 * - `rail.moveUp`/`rail.moveDown` (Alt+↑/↓): the rail row's own keys
 *   (`ChapterRail.tsx`) reordering one chapter.
 */
export const SHORTCUTS: ReadonlyArray<Shortcut> = [
  {
    id: "palette.toggle",
    labelKey: "settings.shortcut.paletteToggle",
    macKey: "shell.paletteKeyMac",
    otherKey: "shell.paletteKeyOther",
    scope: "global",
  },
  {
    id: "workspace.focusDeeper",
    labelKey: "settings.shortcut.focusDeeper",
    macKey: "settings.shortcutKey.f9",
    otherKey: "settings.shortcutKey.f9",
    scope: "workspace",
  },
  {
    id: "workspace.stepBack",
    labelKey: "settings.shortcut.stepBack",
    macKey: "settings.shortcutKey.escape",
    otherKey: "settings.shortcutKey.escape",
    scope: "workspace",
  },
  {
    id: "rail.moveUp",
    labelKey: "settings.shortcut.moveUp",
    macKey: "settings.shortcutKey.reorderUpMac",
    otherKey: "settings.shortcutKey.reorderUpOther",
    scope: "workspace",
  },
  {
    id: "rail.moveDown",
    labelKey: "settings.shortcut.moveDown",
    macKey: "settings.shortcutKey.reorderDownMac",
    otherKey: "settings.shortcutKey.reorderDownOther",
    scope: "workspace",
  },
  {
    id: "editor.acceptGhost",
    labelKey: "settings.shortcut.acceptGhost",
    macKey: "settings.shortcutKey.tab",
    otherKey: "settings.shortcutKey.tab",
    scope: "editor",
  },
  {
    id: "editor.discardGhost",
    labelKey: "settings.shortcut.discardGhost",
    macKey: "settings.shortcutKey.escape",
    otherKey: "settings.shortcutKey.escape",
    scope: "editor",
  },
];

/** The registry row for `id` — unknown ids are a programming error, not a lookup miss. */
export function shortcutById(id: string): Shortcut {
  const found = SHORTCUTS.find((entry) => entry.id === id);
  if (found === undefined) throw new Error(`unknown shortcut: ${id}`);
  return found;
}

/** The platform's own keycap for the binding — the catalog's words, not a literal. */
export function shortcutKeycap(id: string): string {
  const entry = shortcutById(id);
  return t(isMac() ? entry.macKey : entry.otherKey);
}
