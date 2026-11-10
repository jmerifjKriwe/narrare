/**
 * The slash door into the command palette: `/` typed in an empty paragraph
 * opens the palette prefilled with `/`, instead of entering the document.
 *
 * The rule is the paragraph's, not the key's: the caret must sit collapsed
 * at the start of an empty textblock — an empty (or whitespace-only)
 * paragraph with nothing before the caret. A range selection is a
 * replacement, not the door, even when it starts there. Anywhere else the
 * slash is prose, and the handler steps aside so TipTap inserts it
 * normally. No second command surface, no menu: the ask leaves as the
 * shell's one palette event, and the palette is the only list that
 * answers.
 *
 * The slash never reaches the document: handled means ProseMirror inserts
 * nothing, so there is no stray character for Escape to clean up — closing
 * the palette closes the gesture whole.
 */
import { Extension } from "@tiptap/core";
import { Plugin } from "@tiptap/pm/state";

import { requestPaletteOpen } from "@shell/lib/palette";

/** The TipTap extension carrying the slash door's plugin. Stateless. */
export function slashPalette(): Extension {
  return Extension.create({
    name: "slashPalette",
    addProseMirrorPlugins() {
      return [
        new Plugin({
          props: {
            handleKeyDown(view, event) {
              if (event.isComposing) return false;
              if (event.key !== "/") return false;
              // A modified slash is a shortcut's, not the door's.
              if (event.ctrlKey || event.metaKey || event.altKey) return false;
              // A range selection is a replacement, not the door: claiming
              // the key would swallow what the slash should overwrite.
              if (!view.state.selection.empty) return false;
              const { $from } = view.state.selection;
              const parent = $from.parent;
              if (!parent.isTextblock) return false;
              // Whitespace-only is empty: a stray space is not prose.
              if ($from.parentOffset !== 0 || parent.textContent.trim() !== "") return false;
              // The door: claim the key before ProseMirror can insert it,
              // and keep it off the window — no page handler owns "/".
              event.preventDefault();
              event.stopPropagation();
              requestPaletteOpen("/");
              return true;
            },
          },
        }),
      ];
    },
  });
}
