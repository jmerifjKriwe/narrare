/**
 * DialogueMark — TipTap Mark for dialogue spans.
 *
 * Detects dialogue wrapped in quotes (English, French, German) via input/paste rules
 * and applies a visual class. Togglable via Ctrl/Cmd+Shift+D.
 */

import { Mark, markInputRule, markPasteRule, mergeAttributes } from "@tiptap/core";

export const DialogueMark = Mark.create({
  name: "dialogue",

  parseHTML() {
    return [{ tag: "span.dialogue" }];
  },

  renderHTML({ HTMLAttributes }) {
    return ["span", mergeAttributes(HTMLAttributes, { class: "dialogue" }), 0];
  },

  addInputRules() {
    const doubleQuote = /(?:^|\s)("([^"]+)")$/;
    const guillemets = /(?:^|\s)(«([^»]+)»)$/;
    const germanQuotes = /(?:^|\s)(„([^"]+)")$/;

    return [
      markInputRule({ find: doubleQuote, type: this.type }),
      markInputRule({ find: guillemets, type: this.type }),
      markInputRule({ find: germanQuotes, type: this.type }),
    ];
  },

  addPasteRules() {
    return [
      markPasteRule({ find: /"([^"]+)"/g, type: this.type }),
      markPasteRule({ find: /«([^»]+)»/g, type: this.type }),
    ];
  },

  addKeyboardShortcuts() {
    return {
      "Mod-Shift-d": () => this.editor.commands.toggleMark(this.name),
    };
  },
});
