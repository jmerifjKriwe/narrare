import { Editor } from "@tiptap/core";
import type { Node as ProseMirrorNode } from "@tiptap/pm/model";
import StarterKit from "@tiptap/starter-kit";
import { describe, expect, it, vi } from "vitest";
import {
  AIAnnotationExtension,
  AIAnnotationMark,
  acceptMark,
  appendToPendingMark,
  finalizePendingMark,
  getPendingModification,
  hasPendingMark,
  insertAIContent,
  rejectMark,
  resolveAllPendingMarks,
} from "@/components/studio/editor/extensions/AIAnnotation";

// ---------------------------------------------------------------------------
// Helper: create a TipTap editor with our extensions
// ---------------------------------------------------------------------------

function createTestEditor(content = "<p>Hello world</p>"): Editor {
  const element = document.createElement("div");
  document.body.appendChild(element);
  const editor = new Editor({
    element,
    extensions: [StarterKit, AIAnnotationMark, AIAnnotationExtension],
    content,
  });
  return editor;
}

function countPendingMarks(editor: Editor): number {
  let count = 0;
  const markType = editor.state.schema.marks.aiGenerated;
  if (!markType) return 0;
  editor.state.doc.descendants((node: ProseMirrorNode) => {
    if (node.isText) {
      const hasMark = node.marks.some(
        (m) => m.type === markType && (m.attrs as Record<string, string>).status === "pending",
      );
      if (hasMark) count++;
    }
  });
  return count;
}

// ---------------------------------------------------------------------------
// Tests — Standalone functions (primary API)
// ---------------------------------------------------------------------------

describe("AIAnnotationMark", () => {
  it("registers the mark type in the schema", () => {
    const editor = createTestEditor();
    expect(editor.state.schema.marks.aiGenerated).toBeDefined();
    editor.destroy();
  });

  it("raw ProseMirror transaction works", () => {
    const editor = createTestEditor();
    const markType = editor.state.schema.marks.aiGenerated;
    const mark = markType.create({
      requestId: "raw",
      source: "extend",
      originalText: "X",
      status: "pending",
      createdAt: "",
    });
    const pos = 12;
    const { tr } = editor.state;
    tr.insertText("X", pos);
    tr.addMark(pos, pos + 1, mark);
    editor.view.dispatch(tr);
    expect(editor.state.doc.textContent).toContain("X");
    expect(countPendingMarks(editor)).toBe(1);
    editor.destroy();
  });
});

describe("insertAIContent (standalone)", () => {
  it("inserts text with pending mark at cursor", () => {
    const editor = createTestEditor();
    const endPos = editor.state.doc.content.size - 1;
    editor.commands.setTextSelection(endPos);

    insertAIContent(editor, null, "AI text", "req-1", "extend");

    expect(editor.state.doc.textContent).toContain("AI text");
    expect(countPendingMarks(editor)).toBe(1);
    editor.destroy();
  });

  it("resolves existing pending mark before inserting new one", () => {
    const editor = createTestEditor();
    const onAccept = vi.fn();
    const callbacks = { onAccept, onReject: vi.fn(), onModify: vi.fn() };

    const endPos = editor.state.doc.content.size - 1;
    editor.commands.setTextSelection(endPos);
    insertAIContent(editor, callbacks, " first", "req-1", "extend");
    expect(countPendingMarks(editor)).toBe(1);

    const endPos2 = editor.state.doc.content.size - 1;
    editor.commands.setTextSelection(endPos2);
    insertAIContent(editor, callbacks, " second", "req-2", "extend");

    expect(onAccept).toHaveBeenCalledWith("req-1", "extend", " first");
    expect(countPendingMarks(editor)).toBe(1);
    editor.destroy();
  });
});

describe("resolveAllPendingMarks (standalone)", () => {
  it("resolves pending marks and triggers accept callback", () => {
    const editor = createTestEditor();
    const markType = editor.state.schema.marks.aiGenerated;
    const mark = markType.create({
      requestId: "req-save",
      source: "extend",
      originalText: "AI text",
      status: "pending",
      createdAt: "",
    });
    const pos = editor.state.doc.content.size - 1;
    const { tr } = editor.state;
    tr.insertText("AI text", pos);
    tr.addMark(pos, pos + 7, mark);
    editor.view.dispatch(tr);

    expect(countPendingMarks(editor)).toBe(1);

    const onAccept = vi.fn();
    resolveAllPendingMarks(editor, { onAccept, onReject: vi.fn(), onModify: vi.fn() });

    expect(countPendingMarks(editor)).toBe(0);
    expect(onAccept).toHaveBeenCalledWith("req-save", "extend", "AI text");
    expect(editor.state.doc.textContent).toContain("AI text");
    editor.destroy();
  });
});

describe("acceptMark (standalone)", () => {
  it("removes mark but keeps text on accept", () => {
    const editor = createTestEditor("<p>Before</p>");
    const onAccept = vi.fn();
    const callbacks = { onAccept, onReject: vi.fn(), onModify: vi.fn() };

    const endPos = editor.state.doc.content.size - 1;
    editor.commands.setTextSelection(endPos);
    insertAIContent(editor, callbacks, " inserted", "req-accept", "extend");
    expect(editor.state.doc.textContent).toContain("inserted");

    acceptMark(editor, callbacks, "req-accept");
    expect(editor.state.doc.textContent).toContain("inserted");
    expect(countPendingMarks(editor)).toBe(0);
    expect(onAccept).toHaveBeenCalledWith("req-accept", "extend", " inserted");
    editor.destroy();
  });
});

describe("rejectMark (standalone)", () => {
  it("removes text from document on reject", () => {
    const editor = createTestEditor("<p>Before</p>");
    const onReject = vi.fn();
    const callbacks = { onAccept: vi.fn(), onReject, onModify: vi.fn() };

    const endPos = editor.state.doc.content.size - 1;
    editor.commands.setTextSelection(endPos);
    insertAIContent(editor, callbacks, " inserted", "req-reject", "extend");
    expect(editor.state.doc.textContent).toContain("inserted");

    rejectMark(editor, callbacks, "req-reject");
    expect(editor.state.doc.textContent).not.toContain("inserted");
    expect(onReject).toHaveBeenCalledWith("req-reject", "extend", " inserted");
    editor.destroy();
  });
});

describe("appendToPendingMark + finalizePendingMark (standalone)", () => {
  it("appends text to pending mark and finalizes", () => {
    const editor = createTestEditor();
    const endPos = editor.state.doc.content.size - 1;
    editor.commands.setTextSelection(endPos);

    insertAIContent(editor, null, "Hello", "req-stream", "extend");
    expect(editor.state.doc.textContent).toContain("Hello");

    appendToPendingMark(editor, " world");
    expect(editor.state.doc.textContent).toContain("Hello world");

    finalizePendingMark(editor, "Hello world");
    expect(countPendingMarks(editor)).toBe(1);
    editor.destroy();
  });
});

describe("hasPendingMark (standalone)", () => {
  it("returns true when pending mark exists", () => {
    const editor = createTestEditor();
    expect(hasPendingMark(editor)).toBe(false);

    const endPos = editor.state.doc.content.size - 1;
    editor.commands.setTextSelection(endPos);
    insertAIContent(editor, null, "AI text", "req-pending", "extend");

    expect(hasPendingMark(editor)).toBe(true);
    editor.destroy();
  });
});

describe("getPendingModification (standalone)", () => {
  it("detects modification when text within mark changes", () => {
    const editor = createTestEditor();

    const endPos = editor.state.doc.content.size - 1;
    editor.commands.setTextSelection(endPos);
    insertAIContent(editor, null, "AI text", "req-mod", "extend");
    expect(getPendingModification(editor)).toBeNull();

    // Simulate partial edit: insert a character within the mark range
    // (typing within a mark preserves the mark in ProseMirror)
    const markType = editor.state.schema.marks.aiGenerated;
    let markFrom = 0;
    editor.state.doc.descendants((node: ProseMirrorNode, pos: number) => {
      if (node.isText && node.marks.some((m) => m.type === markType)) {
        markFrom = pos;
      }
    });

    // Insert "X" at a position within the mark range (not replacing the whole range)
    // This preserves the mark on the new text
    const insertPos = markFrom + 2; // "AI Xtext"
    const { tr } = editor.state;
    tr.insertText("X", insertPos);
    editor.view.dispatch(tr);

    const mod = getPendingModification(editor);
    expect(mod).not.toBeNull();
    expect(mod?.requestId).toBe("req-mod");
    expect(mod?.current).toContain("X");
    expect(mod?.original).toBe("AI text");
    editor.destroy();
  });

  it("returns null when no pending mark exists", () => {
    const editor = createTestEditor();
    expect(getPendingModification(editor)).toBeNull();
    editor.destroy();
  });
});
