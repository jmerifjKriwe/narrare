"use client";

/**
 * InterviewCompleteState — Completion screen for the KB Interview.
 *
 * Extracted from KBInterviewView for RULE-04 compliance.
 */

import { MessageSquare } from "lucide-react";
import { useTranslations } from "next-intl";

interface InterviewCompleteStateProps {
  onRequestMoreQuestions: () => void;
  onBack: () => void;
}

export function InterviewCompleteState({
  onRequestMoreQuestions,
  onBack,
}: InterviewCompleteStateProps) {
  const t = useTranslations("studio");

  return (
    <div className="text-center py-12">
      <div className="w-16 h-16 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center mx-auto mb-4">
        <MessageSquare className="w-8 h-8 text-green-600 dark:text-green-400" />
      </div>
      <h3 className="text-lg font-medium mb-2">
        {t("kb.interviewComplete") || "Interview Complete"}
      </h3>
      <p className="text-sm text-muted-foreground mb-6">
        {t("kb.interviewCompleteDesc") ||
          "Great! We've gathered enough information. You can review and refine your answers in the field list."}
      </p>
      <div className="flex justify-center gap-3">
        <button
          type="button"
          onClick={onRequestMoreQuestions}
          className="px-4 py-2 border border-border rounded-md hover:bg-muted transition-colors text-sm"
        >
          {t("kb.askMoreQuestions") || "Ask More Questions"}
        </button>
        <button
          type="button"
          onClick={onBack}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity text-sm"
        >
          {t("kb.backToOverview") || "Back to Overview"}
        </button>
      </div>
    </div>
  );
}
