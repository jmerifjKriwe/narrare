/**
 * Command registry for the editor command palette.
 *
 * Each command has an action that receives the TipTap editor and a context
 * object with callbacks for editor-level operations. Generation commands
 * are conditionally visible based on the current generation state.
 */

import type { Editor } from "@tiptap/react";
import type { ComponentType } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CommandState {
  isGenerating: boolean;
  hasDraft: boolean;
  hasPendingAnnotation: boolean;
  hasSelection: boolean;
  selectionLength: number;
}

export interface CommandItem {
  id: string;
  label: string;
  category: "format" | "editor" | "generation";
  icon?: ComponentType<{ size?: number }>;
  shortcut?: string;
  isVisible?: (state: CommandState) => boolean;
  action: (editor: Editor, context: CommandContext) => void;
}

export interface CommandContext {
  toggleSidebar: () => void;
  toggleFocusMode: () => void;
  toggleContextPanel: () => void;
  toggleStoryboard: () => void;
  saveChapter: () => void;
  createChapter: () => void;
  startGeneration: (mode: string) => void;
  stopGeneration: () => void;
  acceptDraft: () => void;
  rejectDraft: () => void;
  toggleGenerationPanel: () => void;
  startExtend: (length: "short" | "medium" | "long") => void;
  startRewrite: () => void;
}

// ---------------------------------------------------------------------------
// Built-in commands
// ---------------------------------------------------------------------------

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
    id: "toggleStoryboard",
    label: "Toggle Storyboard",
    category: "editor",
    action: (_editor, ctx) => ctx.toggleStoryboard(),
  },
  {
    id: "save",
    label: "Save",
    category: "editor",
    shortcut: "⌘S",
    action: (_editor, ctx) => ctx.saveChapter(),
  },
  // Generation commands
  {
    id: "generate-chapter",
    label: "Generate Chapter",
    category: "generation",
    isVisible: (state) => !state.isGenerating && !state.hasDraft,
    action: (_editor, ctx) => ctx.startGeneration("full_draft"),
  },
  {
    id: "generate-outline",
    label: "Generate from Outline",
    category: "generation",
    isVisible: (state) => !state.isGenerating && !state.hasDraft,
    action: (_editor, ctx) => ctx.startGeneration("scene_by_scene"),
  },
  {
    id: "auto-continue",
    label: "Auto-Continue",
    category: "generation",
    isVisible: (state) => !state.isGenerating && !state.hasDraft,
    action: (_editor, ctx) => ctx.startGeneration("interview_assisted"),
  },
  {
    id: "start-session",
    label: "Start Interactive Session",
    category: "generation",
    isVisible: (state) => !state.isGenerating && !state.hasDraft,
    action: (_editor, ctx) => ctx.startGeneration("interactive_session"),
  },
  {
    id: "stop-generation",
    label: "Stop Generation",
    category: "generation",
    isVisible: (state) => state.isGenerating,
    action: (_editor, ctx) => ctx.stopGeneration(),
  },
  {
    id: "accept-draft",
    label: "Accept Draft",
    category: "generation",
    isVisible: (state) => state.hasDraft,
    action: (_editor, ctx) => ctx.acceptDraft(),
  },
  {
    id: "reject-draft",
    label: "Reject Draft",
    category: "generation",
    isVisible: (state) => state.hasDraft,
    action: (_editor, ctx) => ctx.rejectDraft(),
  },
  {
    id: "continue-writing",
    label: "Continue Writing",
    category: "generation",
    isVisible: (state) => !state.isGenerating && !state.hasDraft && !state.hasPendingAnnotation,
    action: (_editor, ctx) => ctx.startExtend("medium"),
  },
  {
    id: "continue-writing-short",
    label: "Continue Writing (Short)",
    category: "generation",
    isVisible: (state) => !state.isGenerating && !state.hasDraft && !state.hasPendingAnnotation,
    action: (_editor, ctx) => ctx.startExtend("short"),
  },
  {
    id: "continue-writing-long",
    label: "Continue Writing (Long)",
    category: "generation",
    isVisible: (state) => !state.isGenerating && !state.hasDraft && !state.hasPendingAnnotation,
    action: (_editor, ctx) => ctx.startExtend("long"),
  },
  {
    id: "rewrite-selection",
    label: "Rewrite Selection",
    category: "generation",
    isVisible: (state) =>
      state.hasSelection && state.selectionLength >= 50 && state.selectionLength <= 2000,
    action: (_editor, ctx) => ctx.startRewrite(),
  },
];
