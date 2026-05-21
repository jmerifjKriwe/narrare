"use client";

import { Star } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useState } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface RatingPromptProps {
  /** The action the user just performed (accept or reject). */
  readonly action: "accept" | "reject";
  /** Callback when user submits rating + optional reason. */
  readonly onSubmit: (data: { rating: number; reason?: string }) => void;
  /** Callback when user dismisses without rating. */
  readonly onDismiss: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function RatingPrompt({ action, onSubmit, onDismiss }: RatingPromptProps) {
  const t = useTranslations("studio");
  const [rating, setRating] = useState(0);
  const [hovered, setHovered] = useState(0);
  const [reason, setReason] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = useCallback(() => {
    if (rating === 0) return;
    onSubmit({ rating, reason: reason.trim() || undefined });
    setSubmitted(true);
  }, [rating, reason, onSubmit]);

  const handleDismiss = useCallback(() => {
    onDismiss();
  }, [onDismiss]);

  if (submitted) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-primary/10 text-primary text-xs">
        <span>✓</span>
        <span>{t("learning.ratingSubmitted")}</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 p-3 rounded-lg border border-border bg-card">
      {/* Star rating */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">{t("learning.rating")}</span>
        <div
          className="flex items-center gap-0.5"
          role="radiogroup"
          aria-label={t("learning.rating")}
        >
          {Array.from({ length: 5 }, (_, i) => {
            const starValue = i + 1;
            const isFilled = starValue <= (hovered || rating);
            return (
              <button
                key={starValue}
                type="button"
                onClick={() => setRating(starValue)}
                onMouseEnter={() => setHovered(starValue)}
                onMouseLeave={() => setHovered(0)}
                className="p-0.5 transition-colors"
                aria-label={`${starValue}`}
              >
                <Star
                  className={`w-4 h-4 ${
                    isFilled
                      ? "fill-yellow-400 text-yellow-400"
                      : "fill-none text-muted-foreground/40"
                  }`}
                />
              </button>
            );
          })}
        </div>
      </div>

      {/* Reject reason (only for reject action) */}
      {action === "reject" && (
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder={t("learning.rejectReason")}
          rows={2}
          className="w-full px-2 py-1.5 text-xs bg-muted/50 border border-border rounded-md resize-none focus:outline-none focus:ring-1 focus:ring-primary"
        />
      )}

      {/* Actions */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={rating === 0}
          className="px-3 py-1 text-xs font-medium rounded-md bg-primary text-primary-foreground hover:opacity-90 transition-opacity disabled:opacity-40"
        >
          {t("learning.submitRating")}
        </button>
        <button
          type="button"
          onClick={handleDismiss}
          className="px-2 py-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          {t("learning.skipRating")}
        </button>
      </div>
    </div>
  );
}
