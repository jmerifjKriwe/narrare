"use client";

import { Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";

import type { CoAuthorFocus } from "@/lib/api/coauthor";

import { btnPrimary, FOCUS_OPTIONS, wordCount } from "./coauthor-styles";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface CoAuthorFocusSelectorProps {
  readonly selectedFocus: CoAuthorFocus[];
  readonly onToggle: (value: CoAuthorFocus) => void;
  readonly selectionText: string;
  readonly onStart: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CoAuthorFocusSelector({
  selectedFocus,
  onToggle,
  selectionText,
  onStart,
}: CoAuthorFocusSelectorProps) {
  const t = useTranslations("studio");

  return (
    <div className="space-y-6">
      <p className="text-sm text-muted-foreground">
        {t("coAuthor.selectionWords", { count: wordCount(selectionText) })}
      </p>
      <div>
        <p className="text-sm font-medium mb-3">{t("coAuthor.focusLabel")}</p>
        <div className="flex flex-wrap gap-2">
          {FOCUS_OPTIONS.map((opt) => {
            const active = selectedFocus.includes(opt.value);
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => onToggle(opt.value)}
                className={`px-4 py-2 text-sm font-medium rounded-lg border transition-colors ${
                  active
                    ? "border-primary bg-primary/10 text-primary shadow-sm"
                    : "border-border hover:border-primary/50 text-foreground"
                }`}
              >
                {t(opt.labelKey)}
              </button>
            );
          })}
        </div>
      </div>
      <button
        type="button"
        onClick={onStart}
        disabled={selectedFocus.length === 0}
        className={`${btnPrimary} flex items-center justify-center gap-2 w-full disabled:opacity-50`}
      >
        <Sparkles className="w-4 h-4" />
        <span>{t("coAuthor.start")}</span>
      </button>
    </div>
  );
}
