/**
 * AI entry points for the editor surface (audits B08/B09).
 *
 * Owns the two AI flows reachable from the editor chrome and joins them into
 * the slash-command handlers that EditorWorkspace forwards to TipTapEditor:
 *
 * - Continue stream: the single `useContinueStream` instance (one stream
 *   owner) shared by the toolbar, the command palette, and the /continue
 *   slash item. Null-safe while the TipTap instance is being created;
 *   `chapterId` falls back to "" because it is null only in the empty-state
 *   branch, where neither the toolbar nor the palette — the only callers of
 *   these handlers — is mounted, so the fallback is unreachable.
 * - Co-author flow: captures the current selection (capped 500-char contexts,
 *   same helper as rewrite — Task 6) to drive the CoAuthorPanel modal overlay.
 *
 * Extracted from EditorView for modularity (RULE-04); pure move of the
 * Task 11/12 wiring, no behavior change.
 *
 * @module useEditorAiEntryPoints
 */

import type { Editor } from "@tiptap/react";
import { useCallback, useMemo, useState } from "react";
import { getSelectionContext } from "../editor/selectionContext";
import type { SlashCommandHandlers } from "../editor/slash-commands";
import { useContinueStream } from "../editor/useContinueStream";

/** Selection captured when the co-author flow (B09) is triggered. */
export interface CoAuthorSelectionState {
  text: string;
  from: number;
  to: number;
  contextBefore: string;
  contextAfter: string;
}

/** Co-author flow state and handlers consumed by the CoAuthorOverlay mount. */
export interface CoAuthorFlow {
  /** Active selection, or null while the panel is closed. */
  readonly selection: CoAuthorSelectionState | null;
  /** Apply the revised text at the captured range and autosave. */
  readonly accept: (revisedText: string) => void;
  /** Close the panel without applying. */
  readonly close: () => void;
}

/** What the editor surface consumes to wire its AI entry points. */
export interface EditorAiEntryPoints {
  /** Continue-stream handlers shared by toolbar, palette, and /continue. */
  readonly continueStream: ReturnType<typeof useContinueStream>;
  /** Co-author flow consumed by CoAuthorOverlay. */
  readonly coAuthor: CoAuthorFlow;
  /** Host handlers forwarded to TipTapEditor via `EditorSurfaceProps`. */
  readonly slashCommandHandlers: Partial<SlashCommandHandlers>;
}

interface UseEditorAiEntryPointsParams {
  /** Nullable: the flows stay untriggerable while the editor mounts. */
  readonly editor: Editor | null;
  readonly novelId: string;
  readonly chapterId: string;
  readonly handleAutosave: (htmlContent: string) => Promise<void>;
}

export function useEditorAiEntryPoints({
  editor,
  novelId,
  chapterId,
  handleAutosave,
}: UseEditorAiEntryPointsParams): EditorAiEntryPoints {
  const continueStream = useContinueStream({ editor, chapterId, novelId });

  // Co-author (B09): capture the selection (capped 500-char contexts, same
  // helper as rewrite — Task 6) and mount the panel as a modal overlay.
  const [coAuthorSelection, setCoAuthorSelection] = useState<CoAuthorSelectionState | null>(null);

  const handleStartCoAuthor = useCallback(() => {
    if (!editor) return;
    const { from, to } = editor.state.selection;
    const text = editor.state.doc.textBetween(from, to, " ");
    if (!text.trim()) return;
    setCoAuthorSelection({ text, from, to, ...getSelectionContext(editor, from, to) });
  }, [editor]);

  const handleCoAuthorAccept = useCallback(
    (revisedText: string) => {
      if (!editor || !coAuthorSelection) return;
      editor
        .chain()
        .focus()
        .insertContentAt({ from: coAuthorSelection.from, to: coAuthorSelection.to }, revisedText)
        .run();
      void handleAutosave(editor.getHTML());
      setCoAuthorSelection(null);
    },
    [editor, coAuthorSelection, handleAutosave],
  );

  const closeCoAuthor = useCallback(() => setCoAuthorSelection(null), []);

  return {
    continueStream,
    coAuthor: {
      selection: coAuthorSelection,
      accept: handleCoAuthorAccept,
      close: closeCoAuthor,
    },
    slashCommandHandlers: useMemo<Partial<SlashCommandHandlers>>(
      () => ({
        onContinue: () => continueStream.handleExtend("medium"),
        onCoAuthor: handleStartCoAuthor,
      }),
      [continueStream.handleExtend, handleStartCoAuthor],
    ),
  };
}
