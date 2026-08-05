"use client";

/**
 * useStructureChangeGuard — encapsulates the "story-structure change requires a
 * remap dialog" guard for NovelDetailsTab.
 *
 * Extracted from NovelDetailsTab (RULE-04) so the tab stays under its file-size
 * limit while still hosting new sections (e.g. the Spec 3 series-voice opt-out
 * card). The hook owns the remap-dialog open/close state and the pending
 * structure value; it exposes ``intercept`` for the save handler to decide
 * whether a save must pause for the remap dialog.
 *
 * The component still owns its LOCAL form state (``localStoryStructure``,
 * ``dirty``) — the hook only owns dialog state. On cancel/close the component
 * resets the local structure + dirty flag itself.
 */
import { useState } from "react";
import type { Novel } from "@/types";

interface UseStructureChangeGuardOptions {
  readonly novel: Novel | undefined;
}

export interface StructureInterception {
  /** True when the save must stop — a remap dialog is now open. */
  readonly intercepted: boolean;
  /**
   * The payload MINUS ``story_structure`` — fields safe to apply immediately
   * alongside opening the remap dialog. Empty when only the structure changed.
   */
  readonly immediatePayload: Partial<Novel>;
}

export function useStructureChangeGuard({ novel }: UseStructureChangeGuardOptions) {
  const [remapDialogOpen, setRemapDialogOpen] = useState(false);
  const [pendingStructure, setPendingStructure] = useState<string | null>(null);

  function intercept(payload: Partial<Novel>): StructureInterception {
    // No guard before the novel has loaded — let the caller save as-is.
    if (!novel) return { intercepted: false, immediatePayload: payload };

    if (payload.story_structure && payload.story_structure !== novel.story_structure) {
      const immediatePayload = { ...payload };
      delete immediatePayload.story_structure;
      setPendingStructure(payload.story_structure);
      setRemapDialogOpen(true);
      return { intercepted: true, immediatePayload };
    }
    return { intercepted: false, immediatePayload: payload };
  }

  /** Close the dialog and clear the pending structure (confirm or cancel). */
  function close() {
    setRemapDialogOpen(false);
    setPendingStructure(null);
  }

  return { remapDialogOpen, pendingStructure, intercept, close };
}
