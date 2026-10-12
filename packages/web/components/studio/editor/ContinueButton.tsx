"use client";

import { ChevronDown, Loader2, PenLine } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import type { ExtendLength } from "@/lib/api/generation";

interface ContinueButtonProps {
  /** Whether a continue/extend stream is active (owned by EditorView). */
  readonly isStreaming: boolean;
  /** Start an extension of the given target length. */
  readonly onExtend: (length: ExtendLength) => void;
  /** Stop the active extension stream. */
  readonly onStop: () => void;
}

export function ContinueButton({ isStreaming, onExtend, onStop }: ContinueButtonProps) {
  const t = useTranslations("studio");
  const [length, setLength] = useState<ExtendLength>("medium");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

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

  return (
    <div className="relative" ref={dropdownRef}>
      <div className="flex items-center">
        <button
          type="button"
          onClick={() => (isStreaming ? onStop() : onExtend(length))}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border border-border bg-card hover:bg-accent transition-colors"
          aria-label={t("annotation.continueWriting")}
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
