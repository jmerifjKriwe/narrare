/**
 * Autosave — TipTap Extension for debounced content saving.
 *
 * Extracts autosave logic from EditorSurface into a reusable extension.
 * Debounces content changes and calls saveFn when content changes.
 * Exposes forceSave via storage for manual save triggers (Cmd+S).
 *
 * Implementation note:
 * TipTap's Extension.create() uses a Proxy for `this`, which prevents closures
 * from dispatching ProseMirror transactions reliably. The resolvePendingMarks
 * logic is therefore exposed as a standalone exported function that takes the
 * editor as an explicit parameter, following the same pattern as aiAnnotationApi.ts.
 */

import { type Editor, Extension } from "@tiptap/core";
import type { Node as ProseMirrorNode } from "@tiptap/pm/model";

export interface AutosaveOptions {
  interval: number;
  saveFn: (content: string) => Promise<void>;
  enabled: boolean;
  /** Called when pending ai-generated marks are implicitly resolved on save. */
  onImplicitAccept?: (data: {
    requestId: string;
    source: string;
    originalText: string;
    action: "accept" | "modify";
    currentText?: string;
  }) => void;
}

export type SaveStatus = "idle" | "saving" | "saved" | "error";

interface AutosaveStorage {
  lastSavedContent: string;
  isSaving: boolean;
  saveStatus: SaveStatus;
  debounceTimer: ReturnType<typeof setTimeout> | null;
  forceSave: () => Promise<void>;
}

// ---------------------------------------------------------------------------
// Standalone function: resolvePendingMarks
// ---------------------------------------------------------------------------
// Extracted from the extension config because TipTap's Extension.create()
// Proxy-based `this` breaks TypeScript inference for custom methods.
// This follows the same pattern as aiAnnotationApi.ts.

/** Remove pending ai-generated marks and trigger implicit accept feedback. */
export function resolvePendingMarks(
  editor: Editor,
  onImplicitAccept?: AutosaveOptions["onImplicitAccept"],
): void {
  const markType = editor.state.schema.marks.aiGenerated;
  if (!markType) return;

  const { tr } = editor.state;
  let hasPending = false;

  editor.state.doc.descendants((node: ProseMirrorNode, pos: number) => {
    if (!node.isText) return;
    const mark = node.marks.find((m) => m.type === markType && m.attrs.status === "pending");
    if (mark) {
      hasPending = true;
      const currentText = editor.state.doc.textBetween(pos, pos + node.nodeSize);
      const originalText = (mark.attrs.originalText as string) || "";
      const requestId = (mark.attrs.requestId as string) || "";
      const source = (mark.attrs.source as string) || "";

      tr.removeMark(pos, pos + node.nodeSize, markType);

      if (onImplicitAccept) {
        const isModified = originalText && currentText !== originalText;
        onImplicitAccept({
          requestId,
          source,
          originalText,
          action: isModified ? "modify" : "accept",
          currentText: isModified ? currentText : undefined,
        });
      }
    }
  });

  if (hasPending) {
    editor.view.dispatch(tr);
  }
}

// ---------------------------------------------------------------------------
// Extension definition
// ---------------------------------------------------------------------------

export const Autosave = Extension.create<AutosaveOptions, AutosaveStorage>({
  name: "autosave",

  addOptions() {
    return {
      interval: 30_000,
      saveFn: async () => {},
      enabled: true,
    };
  },

  addStorage() {
    return {
      lastSavedContent: "",
      isSaving: false,
      saveStatus: "idle" as SaveStatus,
      debounceTimer: null as ReturnType<typeof setTimeout> | null,
      forceSave: async () => {},
    };
  },

  onBeforeCreate() {
    // Bind forceSave to storage so external callers can trigger it
    this.storage.forceSave = async () => {
      // Resolve pending ai-generated marks before saving
      resolvePendingMarks(this.editor, this.options.onImplicitAccept);

      const content = this.editor.getHTML();
      this.storage.isSaving = true;
      this.storage.saveStatus = "saving";
      try {
        await this.options.saveFn(content);
        this.storage.lastSavedContent = content;
        this.storage.saveStatus = "saved";
      } catch {
        this.storage.saveStatus = "error";
      } finally {
        this.storage.isSaving = false;
      }
    };
  },

  onUpdate() {
    if (!this.options.enabled) return;

    const content = this.editor.getHTML();
    if (content === this.storage.lastSavedContent) return;

    this.storage.saveStatus = "idle";

    if (this.storage.debounceTimer) {
      clearTimeout(this.storage.debounceTimer);
    }

    this.storage.debounceTimer = setTimeout(async () => {
      const current = this.editor.getHTML();
      if (current === this.storage.lastSavedContent) return;
      await this.storage.forceSave();
    }, this.options.interval);
  },

  onDestroy() {
    if (this.storage.debounceTimer) {
      clearTimeout(this.storage.debounceTimer);
    }
  },
});
