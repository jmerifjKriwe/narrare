"use client";

/**
 * CR-AUFG-07-24 — Shared, accessible AI rating control.
 *
 * State machine: idle → loading → success | error → (retry → loading) | skipped.
 *
 * The component is a pure controlled view: the host owns lifecycle via
 * `state` and the `onSubmit`/`onSkip`/`onRetry` callbacks. The component's
 * only internal state is the selected rating value and the optional reason
 * text (local interaction state — never persisted to a global store).
 *
 * Accessibility (RULE-16):
 *   - The scale is a `radiogroup` of 5 `radio` inputs (WAI-ARIA Authoring
 *     Practices rating pattern in its radio form — keyboard + screen-reader
 *     friendly, never color-alone).
 *   - The privacy notice lives in an `aria-live="polite"` region so screen
 *     readers announce it after the rating prompt.
 *   - The radio `name` is namespaced per `sourceType`/`sourceId` so two
 *     rating controls on the same page never collide.
 *
 * RULE-16: every visible string is a `studio.aiActions.*` i18n key.
 */

import { useTranslations } from "next-intl";
import { useId, useState } from "react";
import type {
  AIRatingInput,
  AIRatingScale,
  AIRatingState,
  AIRatingViewModel,
} from "@/lib/ai-rating/contracts";

interface AIRatingProps {
  readonly viewModel: AIRatingViewModel;
  readonly state: AIRatingState;
  readonly onSubmit: (input: AIRatingInput) => void;
  readonly onSkip: () => void;
  readonly onRetry: () => void;
}

const SCALE: readonly AIRatingScale[] = [1, 2, 3, 4, 5];

export function AIRating({ viewModel, state, onSubmit, onSkip, onRetry }: AIRatingProps) {
  const t = useTranslations("studio");
  const [value, setValue] = useState<AIRatingScale | null>(null);
  const [reason, setReason] = useState<string>("");
  // Stable, unique radio group name so concurrent controls never collide.
  const reactId = useId();
  const groupName = `${reactId}-rating-${viewModel.sourceType}-${viewModel.sourceId}`;

  if (state === "success") {
    return (
      <p className="text-xs text-muted-foreground" role="status">
        {t("aiActions.ratingSubmitted")}
      </p>
    );
  }

  if (state === "skipped") {
    return <p className="text-xs text-muted-foreground">{t("aiActions.ratingSkipped")}</p>;
  }

  if (state === "error") {
    return (
      <div className="flex items-center gap-2 text-xs">
        <span className="text-red-600 dark:text-red-400" role="alert">
          {t("aiActions.ratingError")}
        </span>
        <button
          type="button"
          onClick={onRetry}
          className="text-primary underline hover:no-underline"
        >
          {t("aiActions.ratingRetry")}
        </button>
        <button
          type="button"
          onClick={onSkip}
          className="ml-auto text-muted-foreground hover:text-foreground"
        >
          {t("aiActions.skipRating")}
        </button>
      </div>
    );
  }

  const disabled = state === "loading";

  return (
    <section
      className="mt-2 rounded-md border border-border/60 p-2 text-xs"
      aria-label={t("aiActions.rating")}
    >
      <div className="flex items-center justify-between gap-2">
        <fieldset className="min-w-0">
          <legend className="sr-only">{t("aiActions.rating")}</legend>
          <div
            role="radiogroup"
            aria-label={t("aiActions.rating")}
            className="flex items-center gap-1"
          >
            {SCALE.map((n) => (
              <label key={n} className="cursor-pointer">
                <input
                  type="radio"
                  name={groupName}
                  value={n}
                  checked={value === n}
                  disabled={disabled}
                  onChange={() => setValue(n)}
                  className="sr-only"
                />
                <span
                  aria-hidden="true"
                  className={`inline-flex h-5 w-5 items-center justify-center rounded border transition-colors ${
                    value === n
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border text-muted-foreground hover:border-primary/50"
                  }`}
                >
                  {n}
                </span>
              </label>
            ))}
          </div>
        </fieldset>
        <span className="text-muted-foreground">
          {state === "loading" ? t("aiActions.ratingSubmitting") : ""}
        </span>
      </div>

      <input
        type="text"
        value={reason}
        disabled={disabled}
        onChange={(e) => setReason(e.target.value)}
        placeholder={t("aiActions.ratingReasonPlaceholder")}
        aria-label={t("aiActions.ratingReason")}
        className="mt-2 w-full rounded border border-border bg-input-background px-2 py-1 text-xs"
      />

      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="text-muted-foreground" aria-live="polite">
          {t("aiActions.ratingPrivacyNotice")}
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onSkip}
            disabled={disabled}
            className="text-muted-foreground hover:text-foreground"
          >
            {t("aiActions.skipRating")}
          </button>
          <button
            type="button"
            onClick={() => value && onSubmit({ rating: value, reason: reason.trim() || undefined })}
            disabled={disabled || value === null}
            className="rounded bg-primary px-2 py-1 text-primary-foreground disabled:opacity-50"
          >
            {t("aiActions.submitRating")}
          </button>
        </div>
      </div>
    </section>
  );
}
