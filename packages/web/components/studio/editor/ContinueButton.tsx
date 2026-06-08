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
import { useAIOperation } from "@/lib/hooks/use-ai-operation";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ContinueButtonProps {
  readonly editor: Editor;
  readonly chapterId: string;
  readonly novelId: string;
  readonly tone?: string;
}

interface ExtendRequestParams {
  readonly textBefore: string;
  readonly textAfter: string | null;
  readonly selectedLength: ExtendLength;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ContinueButton({ editor, chapterId, novelId, tone }: ContinueButtonProps) {
  const t = useTranslations("studio");
  const locale = useLocale();
  const [length, setLength] = useState<ExtendLength>("medium");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const accumulatedRef = useRef("");
  const requestRef = useRef<ExtendRequestParams | null>(null);

  // -- AI operation lifecycle via useAIOperation --

  const { start, cancel, notifyData, isLoading, isStreaming } = useAIOperation<void>({
    execute: (signal) =>
      new Promise<void>((resolve, reject) => {
        const req = requestRef.current;
        if (!req || editor.isDestroyed) {
          resolve();
          return;
        }

        let settled = false;
        let isFirstChunk = true;

        const onAbort = () => {
          if (!settled) {
            settled = true;
            reject(new DOMException("Aborted", "AbortError"));
          }
        };
        signal.addEventListener("abort", onAbort, { once: true });

        streamExtend(
          chapterId,
          novelId,
          {
            text_before: req.textBefore,
            text_after: req.textAfter,
            length: req.selectedLength,
            tone,
            language: locale,
          },
          {
            onChunk: (text) => {
              if (editor.isDestroyed) return;
              if (isFirstChunk) {
                notifyData();
                isFirstChunk = false;
              }

              const localId = `extend-${Date.now()}`;
              if (accumulatedRef.current.length === 0) {
                insertAIContent(editor, null, text, localId, "extend");
              } else {
                appendToPendingMark(editor, text);
              }
              accumulatedRef.current += text;
            },
            onComplete: () => {
              if (!settled) {
                settled = true;
                signal.removeEventListener("abort", onAbort);
                if (!editor.isDestroyed) {
                  finalizePendingMark(editor, accumulatedRef.current);
                }
                resolve();
              }
            },
            onError: (err) => {
              if (!settled) {
                settled = true;
                signal.removeEventListener("abort", onAbort);
                reject(err);
              }
            },
          },
          signal,
        );
      }),
    connectionLossTimeout: 15_000,
  });

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
      if (isLoading || isStreaming) return;
      if (editor.isDestroyed) return;

      const $head = editor.state.selection.$head;
      const textBefore = $head.parent.textContent.slice(0, $head.parentOffset);
      const textAfter = $head.parent.textContent.slice($head.parentOffset);

      requestRef.current = { textBefore, textAfter: textAfter || null, selectedLength };
      accumulatedRef.current = "";
      setDropdownOpen(false);
      start();
    },
    [editor, isLoading, isStreaming, start],
  );

  const handleStop = useCallback(() => {
    cancel();
  }, [cancel]);

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
