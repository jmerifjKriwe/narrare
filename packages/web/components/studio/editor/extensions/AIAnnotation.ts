/**
 * AIAnnotation — TipTap Mark + Extension for tracking AI-generated text.
 *
 * Provides:
 * - `aiGenerated` Mark: ProseMirror mark with attributes (request_id, source,
 *   original_text, status, created_at). Part of the document model, survives
 *   ProseMirror's transaction system.
 * - `aiAnnotation` Extension: Tracker Plugin that enforces single-pending-mark
 *   constraint, position decoration for floating actions UI, and modify detection.
 *   Storage methods are thin wrappers that delegate to standalone functions in
 *   `aiAnnotationApi.ts`.
 *
 * Architecture decision (per WRITE-003, D4):
 * Marks carry arbitrary attributes and survive transactions. The original_text
 * attribute provides a reliable comparison baseline for modify-detection. The
 * Tracker Plugin uses ProseMirror's transaction mapping — no manual position
 * bookkeeping.
 *
 * Implementation note:
 * TipTap's Extension.create() uses a Proxy for `this`, which prevents closures
 * from dispatching ProseMirror transactions reliably. All mutating operations
 * are therefore exposed as standalone exported functions in `aiAnnotationApi.ts`
 * that take the `editor` as an explicit parameter. Storage methods are thin
 * wrappers that look up the editor from `_editorRef` (set in
 * addProseMirrorPlugins).
 *
 * Used by: WRITE-003 (Extend), WRITE-004 (Rewrite), WRITE-009 (Unblock)
 */

import { type Editor, Extension, Mark } from "@tiptap/core";
import { type EditorState, Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";
import {
  type AIAnnotationAttrs,
  acceptMark,
  appendToPendingMark,
  type FeedbackCallbacks,
  finalizePendingMark,
  getPendingModification as getPendingModificationFn,
  hasPendingMark as hasPendingMarkFn,
  insertAIContent,
  type PendingModification,
  rejectMark,
} from "./aiAnnotationApi";

export {
  acceptMark,
  appendToPendingMark,
  finalizePendingMark,
  getPendingModification,
  hasPendingMark,
  insertAIContent,
  rejectMark,
  resolveAllPendingMarks,
} from "./aiAnnotationApi";
// Re-export types and functions for convenience
export type { AIAnnotationAttrs, FeedbackCallbacks, PendingModification };

// ── Storage interface ────────────────────────────────────────────────────────

export interface AIAnnotationStorage {
  /** Stored editor reference — set during addProseMirrorPlugins(). */
  _editorRef: Editor | null;
  _callbacks: FeedbackCallbacks | null;
  _pendingModification: PendingModification | null;
  _accumulatedOriginal: string;

  /** Thin wrappers that delegate to standalone functions via _editorRef. */
  insertAIContent: (text: string, requestId: string, source: string) => void;
  appendToPendingMark: (text: string) => void;
  finalizePendingMark: () => void;
  acceptMark: (requestId: string) => void;
  rejectMark: (requestId: string) => void;
  hasPendingMark: () => boolean;
  getPendingModification: () => PendingModification | null;
  setFeedbackCallbacks: (callbacks: FeedbackCallbacks) => void;
}

// ── Internal helper (shared with aiAnnotationApi) ──────────────────────────

function findPendingMarks(
  state: EditorState,
): { from: number; to: number; attrs: AIAnnotationAttrs }[] {
  const results: { from: number; to: number; attrs: AIAnnotationAttrs }[] = [];
  const markType = state.schema.marks.aiGenerated;
  if (!markType) return results;

  state.doc.descendants((node, pos) => {
    if (!node.isText) return;
    const mark = node.marks.find((m) => m.type === markType && m.attrs.status === "pending");
    if (mark) {
      results.push({
        from: pos,
        to: pos + node.nodeSize,
        attrs: mark.attrs as unknown as AIAnnotationAttrs,
      });
    }
  });
  return results;
}

// ── Mark Definition ────────────────────────────────────────────────────────

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    aiGenerated: {
      setAIAnnotation: (attrs: AIAnnotationAttrs) => ReturnType;
      unsetAIAnnotation: () => ReturnType;
    };
  }
}

export const AIAnnotationMark = Mark.create({
  name: "aiGenerated",

  excludes: "_",
  inclusive: false,

  addAttributes() {
    return {
      requestId: {
        default: null,
        parseHTML: (el: HTMLElement) => el.getAttribute("data-request-id"),
        renderHTML: (attrs: Record<string, unknown>) => ({
          "data-request-id": attrs.requestId as string,
        }),
      },
      source: {
        default: null,
        parseHTML: (el: HTMLElement) => el.getAttribute("data-source"),
        renderHTML: (attrs: Record<string, unknown>) => ({
          "data-source": attrs.source as string,
        }),
      },
      originalText: {
        default: null,
        parseHTML: (el: HTMLElement) => el.getAttribute("data-original-text"),
        renderHTML: (attrs: Record<string, unknown>) => ({
          "data-original-text": attrs.originalText as string,
        }),
      },
      status: {
        default: "pending",
        parseHTML: (el: HTMLElement) => el.getAttribute("data-status") || "pending",
        renderHTML: (attrs: Record<string, unknown>) => ({
          "data-status": (attrs.status as string) || "pending",
        }),
      },
      createdAt: {
        default: null,
        parseHTML: (el: HTMLElement) => el.getAttribute("data-created-at"),
        renderHTML: (attrs: Record<string, unknown>) => ({
          "data-created-at": attrs.createdAt as string,
        }),
      },
    };
  },

  parseHTML() {
    return [{ tag: "span[data-ai-generated]" }];
  },

  renderHTML({ HTMLAttributes }: { HTMLAttributes: Record<string, string> }) {
    const status = HTMLAttributes["data-status"] || "pending";
    return [
      "span",
      {
        "data-ai-generated": "true",
        "data-request-id": HTMLAttributes["data-request-id"] || "",
        "data-source": HTMLAttributes["data-source"] || "",
        "data-original-text": HTMLAttributes["data-original-text"] || "",
        "data-status": status,
        "data-created-at": HTMLAttributes["data-created-at"] || "",
        class: `ai-generated-text ai-generated-${status}`,
      },
      0,
    ];
  },

  addCommands() {
    return {
      setAIAnnotation:
        (attrs) =>
        ({ commands }) =>
          commands.setMark(this.name, attrs),
      unsetAIAnnotation:
        () =>
        ({ commands }) =>
          commands.unsetMark(this.name),
    };
  },
});

// ── Extension (Tracker + Lifecycle) ────────────────────────────────────────

export const AIAnnotationExtension = Extension.create<Record<string, never>, AIAnnotationStorage>({
  name: "aiAnnotation",

  addStorage() {
    return {
      _editorRef: null as Editor | null,
      _callbacks: null as FeedbackCallbacks | null,
      _pendingModification: null as PendingModification | null,
      _accumulatedOriginal: "",

      insertAIContent: () => {},
      appendToPendingMark: () => {},
      finalizePendingMark: () => {},
      acceptMark: () => {},
      rejectMark: () => {},
      hasPendingMark: () => false,
      getPendingModification: () => null as PendingModification | null,
      setFeedbackCallbacks: () => {},
    };
  },

  // ── ProseMirror Plugins ──────────────────────────────────────────────
  // Storage methods are bound here. The editor reference is stored in
  // _editorRef for storage method wrappers to use.

  addProseMirrorPlugins() {
    // Store editor reference for storage method wrappers
    this.storage._editorRef = this.editor;

    // ── Bind storage methods (thin wrappers) ──────────────────────────
    this.storage.insertAIContent = (text: string, requestId: string, source: string) => {
      const editor = this.storage._editorRef;
      if (!editor || editor.isDestroyed) return;
      this.storage._accumulatedOriginal = text;
      this.storage._pendingModification = null;
      insertAIContent(editor, this.storage._callbacks, text, requestId, source);
    };

    this.storage.appendToPendingMark = (text: string) => {
      const editor = this.storage._editorRef;
      if (!editor || editor.isDestroyed) return;
      appendToPendingMark(editor, text);
      this.storage._accumulatedOriginal += text;
    };

    this.storage.finalizePendingMark = () => {
      const editor = this.storage._editorRef;
      if (!editor || editor.isDestroyed) return;
      finalizePendingMark(editor, this.storage._accumulatedOriginal);
    };

    this.storage.acceptMark = (requestId: string) => {
      const editor = this.storage._editorRef;
      if (!editor || editor.isDestroyed) return;
      acceptMark(editor, this.storage._callbacks, requestId);
      this.storage._pendingModification = null;
    };

    this.storage.rejectMark = (requestId: string) => {
      const editor = this.storage._editorRef;
      if (!editor || editor.isDestroyed) return;
      rejectMark(editor, this.storage._callbacks, requestId);
      this.storage._pendingModification = null;
    };

    this.storage.hasPendingMark = () => {
      const editor = this.storage._editorRef;
      if (!editor || editor.isDestroyed) return false;
      return hasPendingMarkFn(editor);
    };

    this.storage.getPendingModification = () => {
      const editor = this.storage._editorRef;
      if (!editor || editor.isDestroyed) return null;
      return getPendingModificationFn(editor);
    };

    this.storage.setFeedbackCallbacks = (callbacks: FeedbackCallbacks) => {
      this.storage._callbacks = callbacks;
    };

    return [
      // AIAnnotationTracker: enforces single-pending-mark + position decoration
      new Plugin({
        key: new PluginKey("aiAnnotationTracker"),

        appendTransaction(_transactions, _oldState, newState) {
          const markType = newState.schema.marks.aiGenerated;
          if (!markType) return null;

          const pending = findPendingMarks(newState);
          if (pending.length <= 1) return null;

          // Auto-resolve all but the newest pending mark
          const tr = newState.tr;
          for (let i = 0; i < pending.length - 1; i++) {
            tr.removeMark(pending[i].from, pending[i].to, markType);
          }
          return tr;
        },

        props: {
          decorations(state: EditorState) {
            const pending = findPendingMarks(state);
            if (pending.length === 0) return DecorationSet.empty;

            const { to, attrs } = pending[0];
            const anchor = document.createElement("span");
            anchor.className = "ai-annotation-anchor";
            anchor.setAttribute("data-request-id", attrs.requestId || "");
            anchor.setAttribute("data-source", attrs.source || "");
            anchor.setAttribute("aria-hidden", "true");

            return DecorationSet.create(state.doc, [
              Decoration.widget(to, anchor, { side: 1, key: "ai-annotation-actions" }),
            ]);
          },
        },
      }),
    ];
  },

  // ── Modify detection ─────────────────────────────────────────────────

  onUpdate() {
    if (this.editor.isDestroyed) return;

    const pending = findPendingMarks(this.editor.state);
    if (pending.length === 0) {
      this.storage._pendingModification = null;
      return;
    }

    const { from, to, attrs } = pending[0];
    const currentText = this.editor.state.doc.textBetween(from, to);
    const originalText = attrs.originalText || "";

    if (originalText && currentText !== originalText) {
      this.storage._pendingModification = {
        original: originalText,
        current: currentText,
        requestId: attrs.requestId,
      };
    } else {
      this.storage._pendingModification = null;
    }
  },
});
