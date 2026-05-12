/**
 * SceneBreak — custom TipTap node for narrative scene breaks.
 *
 * Renders as "* * *" visually.
 * Input rule: typing "---" on an empty line creates a scene break.
 */

import { InputRule, mergeAttributes, Node } from "@tiptap/core";

export const SceneBreak = Node.create({
  name: "sceneBreak",
  group: "block",
  atom: true,

  parseHTML() {
    return [{ tag: "hr.scene-break" }, { tag: "p.scene-break" }];
  },

  renderHTML({ HTMLAttributes }) {
    return ["p", mergeAttributes(HTMLAttributes, { class: "scene-break" }), "* * *"];
  },

  addInputRules() {
    return [
      new InputRule({
        find: /^---$/,
        handler: ({ state, range }) => {
          const { tr } = state;
          const node = this.type.create();
          tr.replaceRangeWith(range.from, range.to, node);
        },
      }),
    ];
  },

  addKeyboardShortcuts() {
    return {
      "Mod-Alt-s": () => this.editor.commands.insertContent({ type: this.name }),
    };
  },
});
