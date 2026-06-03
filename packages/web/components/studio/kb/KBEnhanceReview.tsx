"use client";

/**
 * KB Enhance Review — AI enhancement review interface.
 *
 * Shows before/after comparisons for AI-enhanced fields,
 * with accept/reject per field and bulk actions.
 */

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import type { KBCreationSession, KBEnhancementResult } from "@/lib/api/kb-sessions";

import { EnhanceReviewBulkActions } from "./_components/EnhanceReviewBulkActions";
import { EnhanceReviewCard } from "./_components/EnhanceReviewCard";
import { EnhanceReviewFooter } from "./_components/EnhanceReviewFooter";
import { EnhanceReviewHeader } from "./_components/EnhanceReviewHeader";
import { EnhanceErrorState, EnhanceLoadingState } from "./_components/EnhanceReviewStates";

type EnhanceViewState = "idle" | "loading" | "review" | "error";

interface KBEnhanceReviewProps {
  session: KBCreationSession;
  onRequestEnhance: () => Promise<KBEnhancementResult[]>;
  onAcceptEnhancement: (fieldKey: string, value: string) => void;
  onApplySelected: () => void;
  onBack: () => void;
}

export function KBEnhanceReview({
  session,
  onRequestEnhance,
  onAcceptEnhancement,
  onApplySelected,
  onBack,
}: KBEnhanceReviewProps) {
  const t = useTranslations("studio");
  const [state, setState] = useState<EnhanceViewState>("idle");
  const [enhancements, setEnhancements] = useState<KBEnhancementResult[]>([]);
  const [selectedFieldKeys, setSelectedFieldKeys] = useState<Set<string>>(new Set());
  const [error, setError] = useState<Error | null>(null);

  // --- State management & handlers ---

  function toggleFieldSelection(fieldKey: string) {
    setSelectedFieldKeys((prev) => {
      const next = new Set(prev);
      if (next.has(fieldKey)) {
        next.delete(fieldKey);
      } else {
        next.add(fieldKey);
      }
      return next;
    });
  }

  function selectAll() {
    setSelectedFieldKeys(new Set(enhancements.map((e) => e.field_key)));
  }

  function selectNone() {
    setSelectedFieldKeys(new Set());
  }

  function applySelected() {
    for (const fieldKey of selectedFieldKeys) {
      const enhancement = enhancements.find((e) => e.field_key === fieldKey);
      if (enhancement) {
        onAcceptEnhancement(fieldKey, enhancement.suggested);
      }
    }
    onApplySelected();
  }

  function getFieldLabel(fieldKey: string): string {
    return session.fields.find((f) => f.field_key === fieldKey)?.label || fieldKey;
  }

  async function requestEnhancement() {
    setState("loading");
    setError(null);
    try {
      const results = await onRequestEnhance();
      setEnhancements(results);
      setSelectedFieldKeys(new Set(results.map((e) => e.field_key)));
      setState("review");
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      setState("error");
    }
  }

  // biome-ignore lint/correctness/useExhaustiveDependencies: Runs once on mount — intentional mount-trigger pattern
  useEffect(() => {
    if (state !== "idle") return;
    const run = async () => {
      setState("loading");
      try {
        const results = await onRequestEnhance();
        setEnhancements(results);
        setSelectedFieldKeys(new Set(results.map((e) => e.field_key)));
        setState("review");
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
        setState("error");
      }
    };
    void run();
  }, []);

  // --- Helpers for card accept/reject ---

  function handleCardAccept(fieldKey: string) {
    setSelectedFieldKeys((prev) => new Set(prev).add(fieldKey));
  }

  function handleCardReject(fieldKey: string) {
    setSelectedFieldKeys((prev) => {
      const next = new Set(prev);
      next.delete(fieldKey);
      return next;
    });
  }

  // --- Render ---

  return (
    <div className="flex flex-col h-full">
      <EnhanceReviewHeader
        state={state}
        selectedCount={selectedFieldKeys.size}
        totalCount={enhancements.length}
        onBack={onBack}
        t={t}
      />

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl mx-auto space-y-6">
          {state === "loading" && <EnhanceLoadingState t={t} />}

          {state === "error" && error && (
            <EnhanceErrorState error={error} onRetry={requestEnhancement} t={t} />
          )}

          {state === "review" && (
            <div className="space-y-4">
              <EnhanceReviewBulkActions
                count={enhancements.length}
                onSelectAll={selectAll}
                onSelectNone={selectNone}
                t={t}
              />
              {enhancements.map((enhancement) => (
                <EnhanceReviewCard
                  key={enhancement.field_key}
                  enhancement={enhancement}
                  isSelected={selectedFieldKeys.has(enhancement.field_key)}
                  onToggle={toggleFieldSelection}
                  onAccept={handleCardAccept}
                  onReject={handleCardReject}
                  fieldLabel={getFieldLabel(enhancement.field_key)}
                  t={t}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {state === "review" && (
        <EnhanceReviewFooter
          selectedCount={selectedFieldKeys.size}
          onBack={onBack}
          onRejectAll={selectNone}
          onApply={applySelected}
          t={t}
        />
      )}
    </div>
  );
}
