"use client";

import type { Editor } from "@tiptap/react";
import { useEffect, useRef, useState } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface PendingMarkInfo {
  requestId: string;
  source: string;
  wordCount: number;
  originalText: string;
  currentText: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function findPendingMarkInfo(editor: Editor): PendingMarkInfo | null {
  const markType = editor.state.schema.marks.aiGenerated;
  if (!markType) return null;

  let info: PendingMarkInfo | null = null;
  editor.state.doc.descendants((node, pos) => {
    if (info) return false;
    if (!node.isText) return;
    const mark = node.marks.find((m) => m.type === markType && m.attrs.status === "pending");
    if (mark) {
      const text = editor.state.doc.textBetween(pos, pos + node.nodeSize);
      info = {
        requestId: (mark.attrs.requestId as string) || "",
        source: (mark.attrs.source as string) || "extend",
        wordCount: text.split(/\s+/).filter(Boolean).length,
        originalText: (mark.attrs.originalText as string) || "",
        currentText: text,
      };
      return false;
    }
  });
  return info;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

interface UseAnnotationMarkTrackerOptions {
  readonly editor: Editor;
  readonly showRating: "accept" | "reject" | null;
  readonly setShowRating: (rating: "accept" | "reject" | null) => void;
}

/** Detects pending AI annotation marks and tracks floating action position. */
export function useAnnotationMarkTracker({
  editor,
  showRating,
  setShowRating,
}: UseAnnotationMarkTrackerOptions) {
  const [markInfo, setMarkInfo] = useState<PendingMarkInfo | null>(null);
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Track pending mark changes
  useEffect(() => {
    const updateState = () => {
      const info = findPendingMarkInfo(editor);
      if (info) {
        setMarkInfo(info);
        // Hide rating when new mark appears
        setShowRating(null);
      } else if (!showRating) {
        setMarkInfo(null);
      }
    };

    updateState();
    editor.on("update", updateState);
    editor.on("transaction", updateState);
    return () => {
      editor.off("update", updateState);
      editor.off("transaction", updateState);
    };
  }, [editor, showRating, setShowRating]);

  // Position floating actions near the anchor decoration
  useEffect(() => {
    if (!markInfo) {
      setPosition(null);
      return;
    }

    const updatePosition = () => {
      const anchor = document.querySelector(".ai-annotation-anchor");
      if (!anchor) return;

      const anchorRect = anchor.getBoundingClientRect();
      const containerWidth = containerRef.current?.offsetWidth || 280;

      setPosition({
        top: anchorRect.bottom + 8,
        left: Math.max(
          8,
          Math.min(anchorRect.left - containerWidth / 2, window.innerWidth - containerWidth - 8),
        ),
      });
    };

    updatePosition();
    window.addEventListener("resize", updatePosition);
    // Re-position on scroll within the editor
    const editorEl = editor.view.dom.closest(".overflow-y-auto, [class*=overflow]");
    if (editorEl) editorEl.addEventListener("scroll", updatePosition);

    return () => {
      window.removeEventListener("resize", updatePosition);
      if (editorEl) editorEl.removeEventListener("scroll", updatePosition);
    };
  }, [markInfo, editor]);

  return { markInfo, setMarkInfo, position, containerRef };
}
