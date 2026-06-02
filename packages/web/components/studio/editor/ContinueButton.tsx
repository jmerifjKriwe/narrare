"use client";

import type { Editor } from "@tiptap/react";
import { ChevronDown, Loader2, PenLine } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  appendToPendingMark,
  finalizePendingMark,
  insertAIContent,
} from "@/components/studio/editor/extensions/AIAnnotation";
import { type ExtendLength, streamExtend } from "@/lib/api/generation";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ContinueButtonProps {
  readonly editor: Editor;
  readonly chapterId: string;
  readonly novelId: string;
  readonly tone?: string;
}

type ExtendPhase = "idle" | "streaming";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ContinueButton({ editor, chapterId, novelId, tone }: ContinueButtonProps) {
  const t = useTranslations("studio");
  const locale = useLocale();
  const [length, setLength] = useState<ExtendLength>("medium");
  const [phase, setPhase] = useState<ExtendPhase>("idle");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const accumulatedRef = useRef("");

  // Close dropdown on outside click
  useEffect(() => {
    if (!dropdownOpen) return;
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [dropdownOpen]);

  const handleExtend = useCallback(
    (selectedLength: ExtendLength) => {
      if (phase === "streaming") return;
      if (editor.isDestroyed) return;

      const $head = editor.state.selection.$head;
      const textBefore = $head.parent.textContent.slice(0, $head.parentOffset);
      const textAfter = $head.parent.textContent.slice($head.parentOffset);

      setPhase("streaming");
      setDropdownOpen(false);
      accumulatedRef.current = "";

      const controller = new AbortController();
      abortRef.current = controller;

      let isFirstChunk = true;

      streamExtend(
        chapterId,
        novelId,
        {
          text_before: textBefore,
          text_after: textAfter || null,
          length: selectedLength,
          tone,
          language: locale,
        },
        {
          onRequestInfo: () => {
            // Request ID received from first SSE event
          },
          onChunk: (text) => {
            if (editor.isDestroyed) return;

            if (isFirstChunk) {
              const localId = `extend-${Date.now()}`;
              insertAIContent(editor, null, text, localId, "extend");
              accumulatedRef.current = text;
              isFirstChunk = false;
            } else {
              appendToPendingMark(editor, text);
              accumulatedRef.current += text;
            }
          },
          onComplete: () => {
            if (!editor.isDestroyed) {
              finalizePendingMark(editor, accumulatedRef.current);
            }
            setPhase("idle");
            abortRef.current = null;
          },
          onError: () => {
            setPhase("idle");
            abortRef.current = null;
          },
        },
        controller.signal,
      );
    },
    [editor, chapterId, novelId, tone, locale, phase],
  );

  const handleStop = useCallback(() => {
    abortRef.current?.abort();
    setPhase("idle");
    abortRef.current = null;
  }, []);

  const isStreaming = phase === "streaming";

  return (
    <div className="relative" ref={dropdownRef}>
      <div className="flex items-center">
        <button
          type="button"
          onClick={() => (isStreaming ? handleStop() : handleExtend(length))}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border border-border bg-card hover:bg-accent transition-colors"
          aria-label={t("annotation.continueWriting")}
          disabled={editor.isDestroyed}
        >
          {isStreaming ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>{t("aiActions.stop")}</span>
            </>
          ) : (
            <>
              <PenLine className="w-3.5 h-3.5" />
              <span>{t("annotation.continueWriting")}</span>
            </>
          )}
        </button>
        {!isStreaming && (
          <button
            type="button"
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="flex items-center px-1 py-1.5 text-xs rounded-r-md border border-l-0 border-border bg-card hover:bg-accent transition-colors"
            aria-label={t("annotation.selectLength")}
          >
            <ChevronDown className="w-3 h-3" />
          </button>
        )}
      </div>

      {dropdownOpen && !isStreaming && (
        <div className="absolute top-full left-0 mt-1 w-36 bg-card border border-border rounded-lg shadow-lg overflow-hidden z-50">
          {(["short", "medium", "long"] as const).map((len) => (
            <button
              key={len}
              type="button"
              onClick={() => {
                setLength(len);
                setDropdownOpen(false);
              }}
              className={`w-full text-left px-3 py-2 text-xs transition-colors ${
                length === len ? "bg-accent font-medium" : "hover:bg-accent"
              }`}
            >
              {t(`annotation.length.${len}`)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
