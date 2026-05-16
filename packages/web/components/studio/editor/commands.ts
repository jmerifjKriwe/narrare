/**
 * Command registry for the editor command palette.
 *
 * Each command has an action that receives the TipTap editor and a context
 * object with callbacks for editor-level operations. AI features will add
 * commands here in the future.
 */

import type { Editor } from "@tiptap/react";
import type { ComponentType } from "react";

export interface CommandItem {
  id: string;
  label: string;
  category: "format" | "editor";
  icon?: ComponentType<{ size?: number }>;
  shortcut?: string;
  action: (editor: Editor, context: CommandContext) => void;
}

export interface CommandContext {
  toggleSidebar: () => void;
  toggleFocusMode: () => void;
  toggleContextPanel: () => void;
  saveChapter: () => void;
  createChapter: () => void;
}

export const builtInCommands: CommandItem[] = [
  // Formatting
  {
    id: "bold",
    label: "Bold",
    category: "format",
    shortcut: "⌘B",
    action: (editor) => editor.chain().focus().toggleBold().run(),
  },
  {
    id: "italic",
    label: "Italic",
    category: "format",
    shortcut: "⌘I",
    action: (editor) => editor.chain().focus().toggleItalic().run(),
  },
  {
    id: "heading1",
    label: "Heading 1",
    category: "format",
    shortcut: "⌘⇧1",
    action: (editor) => editor.chain().focus().toggleHeading({ level: 1 }).run(),
  },
  {
    id: "heading2",
    label: "Heading 2",
    category: "format",
    shortcut: "⌘⇧2",
    action: (editor) => editor.chain().focus().toggleHeading({ level: 2 }).run(),
  },
  {
    id: "heading3",
    label: "Heading 3",
    category: "format",
    shortcut: "⌘⇧3",
    action: (editor) => editor.chain().focus().toggleHeading({ level: 3 }).run(),
  },
  {
    id: "sceneBreak",
    label: "Scene Break",
    category: "format",
    shortcut: "⌘⌥S",
    action: (editor) => editor.commands.insertContent({ type: "sceneBreak" }),
  },
  // Editor actions
  {
    id: "toggleSidebar",
    label: "Toggle Sidebar",
    category: "editor",
    shortcut: "⌘\\",
    action: (_editor, ctx) => ctx.toggleSidebar(),
  },
  {
    id: "toggleFocusMode",
    label: "Focus Mode",
    category: "editor",
    shortcut: "⌘⇧F",
    action: (_editor, ctx) => ctx.toggleFocusMode(),
  },
  {
    id: "togglePanel",
    label: "Toggle Context Panel",
    category: "editor",
    action: (_editor, ctx) => ctx.toggleContextPanel(),
  },
  {
    id: "save",
    label: "Save",
    category: "editor",
    shortcut: "⌘S",
    action: (_editor, ctx) => ctx.saveChapter(),
  },
];
