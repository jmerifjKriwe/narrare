"use client";

import { Check, FileText, Image, MessageSquare, Type, X } from "lucide-react";
import { useTranslations } from "next-intl";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ChangeReviewProps {
  readonly change: {
    id: string;
    change_type: string; // "word_choice" | "sentence" | "dialogue" | "description"
    original_text: string;
    revised_text: string;
    index: number;
  };
  readonly isAccepted: boolean;
  readonly onToggle?: (changeId: string) => void;
  readonly readOnly?: boolean;
}

// ---------------------------------------------------------------------------
// Change type metadata
// ---------------------------------------------------------------------------

interface ChangeTypeMeta {
  labelKey: string;
  icon: React.ReactNode;
  bgClass: string;
  textClass: string;
}

function getChangeTypeMeta(changeType: string): ChangeTypeMeta {
  switch (changeType) {
    case "word_choice":
      return {
        labelKey: "Word Choice",
        icon: <Type className="w-3 h-3" />,
        bgClass: "bg-blue-100 dark:bg-blue-900/30",
        textClass: "text-blue-700 dark:text-blue-300",
      };
    case "sentence":
      return {
        labelKey: "Sentence",
        icon: <FileText className="w-3 h-3" />,
        bgClass: "bg-purple-100 dark:bg-purple-900/30",
        textClass: "text-purple-700 dark:text-purple-300",
      };
    case "dialogue":
      return {
        labelKey: "Dialogue",
        icon: <MessageSquare className="w-3 h-3" />,
        bgClass: "bg-amber-100 dark:bg-amber-900/30",
        textClass: "text-amber-700 dark:text-amber-300",
      };
    case "description":
      return {
        labelKey: "Description",
        icon: <Image className="w-3 h-3" />,
        bgClass: "bg-green-100 dark:bg-green-900/30",
        textClass: "text-green-700 dark:text-green-300",
      };
    default:
      return {
        labelKey: changeType,
        icon: <FileText className="w-3 h-3" />,
        bgClass: "bg-muted",
        textClass: "text-muted-foreground",
      };
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ChangeReview({
  change,
  isAccepted,
  onToggle,
  readOnly = false,
}: ChangeReviewProps) {
  const t = useTranslations("studio");
  const meta = getChangeTypeMeta(change.change_type);

  return (
    <div
      className={`rounded-lg border transition-all ${
        isAccepted ? "border-green-500/50 bg-green-500/5" : "border-border hover:border-primary/30"
      }`}
    >
      {/* Header row: type badge + accept/reject toggle */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border/50">
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${meta.bgClass} ${meta.textClass}`}
          >
            {meta.icon}
            <span>{meta.labelKey}</span>
          </span>
          <span className="text-xs text-muted-foreground">#{change.index + 1}</span>
        </div>

        {!readOnly && onToggle && (
          <button
            type="button"
            onClick={() => onToggle(change.id)}
            className={`flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-md transition-all ${
              isAccepted
                ? "bg-green-500/10 text-green-600 dark:text-green-400 hover:bg-green-500/20"
                : "bg-muted text-muted-foreground hover:bg-accent"
            }`}
            aria-label={isAccepted ? "Reject change" : "Accept change"}
          >
            {isAccepted ? (
              <>
                <Check className="w-3 h-3" />
                <span>{t("changeReview.accepted")}</span>
              </>
            ) : (
              <>
                <X className="w-3 h-3" />
                <span>{t("changeReview.rejected")}</span>
              </>
            )}
          </button>
        )}
      </div>

      {/* Diff content: original (red strikethrough) → revised (green) */}
      <div className="px-3 py-2.5 text-sm leading-relaxed space-y-1.5">
        <div className="flex items-start gap-2">
          <span className="text-xs font-medium text-muted-foreground w-16 flex-shrink-0 pt-0.5">
            {t("changeReview.original")}
          </span>
          <span className="bg-red-200/60 dark:bg-red-900/40 line-through rounded-sm px-0.5">
            {change.original_text}
          </span>
        </div>
        <div className="flex items-start gap-2">
          <span className="text-xs font-medium text-muted-foreground w-16 flex-shrink-0 pt-0.5">
            {t("changeReview.revised")}
          </span>
          <span className="bg-green-200/60 dark:bg-green-900/40 rounded-sm px-0.5">
            {change.revised_text}
          </span>
        </div>
      </div>
    </div>
  );
}
