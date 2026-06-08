"use client";

/**
 * KB Enhance Review — AI enhancement review interface.
 *
 * Shows before/after comparisons for AI-enhanced fields,
 * with accept/reject per field and bulk actions.
 *
 * Uses useAIOperation for lifecycle management (§16).
 */

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import type { KBCreationSession, KBEnhancementResult } from "@/lib/api/kb-sessions";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";

import { EnhanceReviewBulkActions } from "./_components/EnhanceReviewBulkActions";
import { EnhanceReviewCard } from "./_components/EnhanceReviewCard";
import { EnhanceReviewFooter } from "./_components/EnhanceReviewFooter";
import { EnhanceReviewHeader } from "./_components/EnhanceReviewHeader";
import { EnhanceErrorState, EnhanceLoadingState } from "./_components/EnhanceReviewStates";

type EnhancePhase = "idle" | "review" | "complete";

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
  const [phase, setPhase] = useState<EnhancePhase>("idle");
  const [enhancements, setEnhancements] = useState<KBEnhancementResult[]>([]);
  const [selectedFieldKeys, setSelectedFieldKeys] = useState<Set<string>>(new Set());

  // --- AI operation lifecycle via useAIOperation ---
  const enhanceOp = useAIOperation<KBEnhancementResult[]>({
    execute: () => onRequestEnhance(),
    onSuccess: (results) => {
      setEnhancements(results);
      setSelectedFieldKeys(new Set(results.map((e) => e.field_key)));
      setPhase("review");
    },
  });

  // Start on mount
  // biome-ignore lint/correctness/useExhaustiveDependencies: Runs once on mount — intentional mount-trigger pattern
  useEffect(() => {
    if (phase !== "idle") return;
    enhanceOp.start();
  }, []);

  // --- Selection management ---

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

  // --- Derive display state ---
  const isLoading = enhanceOp.isLoading || enhanceOp.isStreaming;
  const isError = enhanceOp.isError || enhanceOp.isConnectionLost;
  const error = enhanceOp.state.error;

  // --- Render ---

  return (
    <div className="flex flex-col h-full">
      <EnhanceReviewHeader
        state={isLoading ? "loading" : isError ? "error" : phase === "review" ? "review" : "idle"}
        selectedCount={selectedFieldKeys.size}
        totalCount={enhancements.length}
        onBack={onBack}
        t={t}
      />

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl mx-auto space-y-6">
          {isLoading && <EnhanceLoadingState t={t} onCancel={enhanceOp.cancel} />}

          {enhanceOp.isConnectionLost && error && (
            <EnhanceErrorState error={error} onRetry={enhanceOp.retry} t={t} />
          )}

          {isError && !enhanceOp.isConnectionLost && error && (
            <EnhanceErrorState error={error} onRetry={enhanceOp.retry} t={t} />
          )}

          {phase === "review" && (
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

      {phase === "review" && (
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
