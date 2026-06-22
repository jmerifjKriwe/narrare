/**
 * Public types for :func:`usePromptEditorState`.
 *
 * Extracted into a sibling file so the hook itself stays under the RULE-04
 * 150-line hook limit. The component layer imports both.
 */

import type { UseMutationResult } from "@tanstack/react-query";
import type { PromptDetail, PromptPreview, PromptResetResult } from "@/types";

export interface StatusMessage {
  readonly type: "success" | "error";
  readonly text: string;
}

export interface UsePromptEditorStateReturn {
  // Prompt fetch
  readonly prompt: PromptDetail | undefined;
  readonly isLoading: boolean;
  readonly error: unknown;
  // Edit mode
  readonly editMode: boolean;
  readonly editedContent: string;
  readonly setEditMode: (v: boolean) => void;
  readonly setEditedContent: (v: string) => void;
  readonly handleStartEdit: () => void;
  readonly handleSave: () => void;
  readonly saveMutation: UseMutationResult<void, Error, string, unknown>;
  // Reset
  readonly showResetConfirm: boolean;
  readonly setShowResetConfirm: (v: boolean) => void;
  readonly resetMutation: UseMutationResult<PromptResetResult, Error, void, unknown>;
  // Diff
  readonly showDiff: boolean;
  readonly openDiff: () => void;
  readonly closeDiff: () => void;
  // Preview (PROMPT-003)
  readonly showPreviewDialog: boolean;
  readonly setShowPreviewDialog: (v: boolean) => void;
  readonly preview: PromptPreview | undefined;
  readonly previewLoading: boolean;
  // Live test (PROMPT-003)
  readonly showLiveTestDialog: boolean;
  readonly setShowLiveTestDialog: (v: boolean) => void;
  readonly liveTestAcknowledged: boolean;
  readonly liveTestOutput: string;
  readonly liveTestStreaming: boolean;
  readonly liveTestError: string | null;
  readonly handleConfirmLiveTest: () => void;
  readonly handleCancelLiveTest: () => void;
  // Status
  readonly statusMessage: StatusMessage | null;
}
