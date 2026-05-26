"use client";

/**
 * FeedbackCard — displays a single feedback item, strength, or question.
 *
 * Supports three variants:
 * - "feedback": BetaFeedbackItem with severity badge, category, suggestion
 * - "strength": BetaReaderStrength with green tint
 * - "question": BetaReaderQuestion with blue tint
 *
 * All text excerpts are collapsible. Uses i18n for labels.
 */

import { ChevronDown, ChevronUp, Lightbulb, MapPin } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import type {
  BetaFeedbackItem,
  BetaReaderQuestion,
  BetaReaderStrength,
  FeedbackCategory,
  FeedbackSeverity,
} from "@/lib/api/analysis";

// --- Severity badge color mapping ---

const SEVERITY_COLORS: Record<FeedbackSeverity, string> = {
  critical: "bg-red-100 text-red-700 dark:bg-red-950/30 dark:text-red-400",
  moderate: "bg-amber-100 text-amber-700 dark:bg-amber-950/30 dark:text-amber-400",
  minor: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
};

const SEVERITY_DOT: Record<FeedbackSeverity, string> = {
  critical: "bg-red-500",
  moderate: "bg-amber-500",
  minor: "bg-gray-400",
};

const CATEGORY_COLORS: Record<FeedbackCategory, string> = {
  plot: "bg-blue-100 text-blue-700 dark:bg-blue-950/30 dark:text-blue-400",
  character: "bg-purple-100 text-purple-700 dark:bg-purple-950/30 dark:text-purple-400",
  prose: "bg-teal-100 text-teal-700 dark:bg-teal-950/30 dark:text-teal-400",
  pacing: "bg-orange-100 text-orange-700 dark:bg-orange-950/30 dark:text-orange-400",
  experience: "bg-pink-100 text-pink-700 dark:bg-pink-950/30 dark:text-pink-400",
};

// --- Variant tint ---

const VARIANT_TINT: Record<string, string> = {
  feedback: "border-l-2 border-l-red-400 dark:border-l-red-500",
  strength:
    "border-l-2 border-l-green-400 dark:border-l-green-500 bg-green-50/50 dark:bg-green-950/10",
  question: "border-l-2 border-l-blue-400 dark:border-l-blue-500 bg-blue-50/50 dark:bg-blue-950/10",
};

// --- Types ---

type FeedbackCardItem =
  | ({ _variant: "feedback" } & BetaFeedbackItem)
  | ({ _variant: "strength" } & BetaReaderStrength)
  | ({ _variant: "question" } & BetaReaderQuestion);

interface FeedbackCardProps {
  /** The feedback item to display. Use createCardItem() helpers. */
  item: FeedbackCardItem;
}

// --- Helpers to create typed card items ---

export function feedbackCardItem(item: BetaFeedbackItem): FeedbackCardItem {
  return { ...item, _variant: "feedback" };
}

export function strengthCardItem(item: BetaReaderStrength): FeedbackCardItem {
  return { ...item, _variant: "strength" };
}

export function questionCardItem(item: BetaReaderQuestion): FeedbackCardItem {
  return { ...item, _variant: "question" };
}

// --- Component ---

export function FeedbackCard({ item }: FeedbackCardProps) {
  const t = useTranslations("analysis");
  const [excerptOpen, setExcerptOpen] = useState(false);

  const variant = item._variant;
  const isFeedback = variant === "feedback";
  const isStrength = variant === "strength";
  const isQuestion = variant === "question";

  // Extract common fields
  const category = item.category;
  const title = isQuestion
    ? (item as BetaReaderQuestion).question
    : (item as BetaFeedbackItem | BetaReaderStrength).title;
  const description = isFeedback
    ? (item as BetaFeedbackItem).description
    : isStrength
      ? (item as BetaReaderStrength).description
      : ((item as BetaReaderQuestion).context ?? "");

  // Feedback-specific fields
  const severity = isFeedback ? (item as BetaFeedbackItem).severity : null;
  const suggestion = isFeedback ? (item as BetaFeedbackItem).suggestion : null;
  const location = isFeedback
    ? (item as BetaFeedbackItem).location
    : isQuestion
      ? (item as BetaReaderQuestion).location
      : null;

  // Common excerpt field
  const textExcerpt = isFeedback
    ? (item as BetaFeedbackItem).text_excerpt
    : isStrength
      ? (item as BetaReaderStrength).text_excerpt
      : null;

  return (
    <div className={`rounded-lg border border-border p-4 ${VARIANT_TINT[variant]}`}>
      {/* Header: badges + title */}
      <div className="flex items-start gap-2 mb-2">
        {severity && (
          <span
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${SEVERITY_COLORS[severity]}`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${SEVERITY_DOT[severity]}`} />
            {t(`severity.${severity}`)}
          </span>
        )}
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${CATEGORY_COLORS[category]}`}>
          {t(`categories.${category}`)}
        </span>
      </div>

      {/* Title */}
      <h4 className="font-medium text-sm mb-1">{title}</h4>

      {/* Description */}
      {description && <p className="text-sm text-muted-foreground mb-2">{description}</p>}

      {/* Location */}
      {location && (
        <div className="flex items-center gap-1 text-xs text-muted-foreground mb-2">
          <MapPin className="w-3 h-3" />
          <span>{location}</span>
        </div>
      )}

      {/* Suggestion */}
      {suggestion && (
        <div className="mt-2 p-2 rounded bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/50">
          <div className="flex items-center gap-1 text-xs font-medium text-amber-700 dark:text-amber-400 mb-1">
            <Lightbulb className="w-3 h-3" />
            {t("suggestion")}
          </div>
          <p className="text-xs text-amber-800 dark:text-amber-300">{suggestion}</p>
        </div>
      )}

      {/* Collapsible text excerpt */}
      {textExcerpt && (
        <div className="mt-2">
          <button
            type="button"
            onClick={() => setExcerptOpen(!excerptOpen)}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
            aria-expanded={excerptOpen}
          >
            {excerptOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            {excerptOpen ? t("excerpt.hide") : t("excerpt.show")}
          </button>
          {excerptOpen && (
            <blockquote className="mt-1 pl-3 border-l-2 border-muted text-xs italic text-muted-foreground">
              {textExcerpt}
            </blockquote>
          )}
        </div>
      )}
    </div>
  );
}
