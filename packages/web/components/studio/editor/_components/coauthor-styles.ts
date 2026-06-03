import type { CoAuthorFocus } from "@/lib/api/coauthor";

// ---------------------------------------------------------------------------
// Shared types
// ---------------------------------------------------------------------------

export type CoAuthorPhase = "focus" | "streaming" | "review" | "done" | "error";

// ---------------------------------------------------------------------------
// Shared constants & utilities for CoAuthor sub-components
// ---------------------------------------------------------------------------

export const wordCount = (text: string): number => text.trim().split(/\s+/).filter(Boolean).length;

export const FOCUS_OPTIONS: { value: CoAuthorFocus; labelKey: string }[] = [
  { value: "word_choice", labelKey: "coAuthor.focusWordChoice" },
  { value: "sentence", labelKey: "coAuthor.focusSentence" },
  { value: "dialogue", labelKey: "coAuthor.focusDialogue" },
  { value: "description", labelKey: "coAuthor.focusDescription" },
];

// Button styles
const btnBase = "px-4 py-2.5 text-sm rounded-lg transition-all";
export const btnPrimary = `${btnBase} bg-primary text-primary-foreground hover:opacity-90 shadow-sm font-medium`;
export const btnSecondary = `${btnBase} border border-border hover:bg-accent`;
export const btnSm = "px-3 py-1 text-xs font-medium rounded-md transition-all";
