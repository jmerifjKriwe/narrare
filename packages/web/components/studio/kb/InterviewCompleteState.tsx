"use client";

/**
 * InterviewCompleteState — Completion screen for the KB Interview.
 *
 * Renders the success message and action buttons, plus an optional,
 * collapsible Q&A history timeline (InterviewHistory) so the user can
 * review and search the recorded questions and answers.
 *
 * Extracted from KBInterviewView for RULE-04 compliance.
 */

import { MessageSquare } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import type { KBCreationField } from "@/lib/api/kb-sessions";
import type { InterviewQAEntry } from "@/lib/hooks/use-interview-history";
import { InterviewHistory } from "./InterviewHistory";

interface InterviewCompleteStateProps {
  onRequestMoreQuestions: () => void;
  onBack: () => void;
  /** Recorded Q&A pairs from the interview session. */
  readonly history: readonly InterviewQAEntry[];
  /** Session fields — forwarded to InterviewHistory for badge labels. */
  readonly fields: readonly KBCreationField[];
}

export function InterviewCompleteState({
  onRequestMoreQuestions,
  onBack,
  history,
  fields,
}: InterviewCompleteStateProps) {
  const t = useTranslations("studio");
  const [showHistory, setShowHistory] = useState(false);

  return (
    <div className="text-center py-12">
      <div className="w-16 h-16 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center mx-auto mb-4">
        <MessageSquare className="w-8 h-8 text-green-600 dark:text-green-400" />
      </div>
      <h3 className="text-lg font-medium mb-2">{t("kb.interviewComplete")}</h3>
      <p className="text-sm text-muted-foreground mb-6">{t("kb.interviewCompleteDesc")}</p>
      <div className="flex justify-center gap-3">
        <button
          type="button"
          onClick={onRequestMoreQuestions}
          className="px-4 py-2 border border-border rounded-md hover:bg-muted transition-colors text-sm"
        >
          {t("kb.askMoreQuestions")}
        </button>
        <button
          type="button"
          onClick={onBack}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity text-sm"
        >
          {t("kb.backToOverview")}
        </button>
      </div>

      {history.length > 0 && (
        <div className="mt-6">
          <button
            type="button"
            onClick={() => setShowHistory((prev) => !prev)}
            className="text-xs text-muted-foreground hover:text-foreground underline underline-offset-2"
          >
            {showHistory ? t("kb.hideInterviewHistory") : t("kb.showInterviewHistory")}
          </button>

          {showHistory && (
            <div className="mt-3 text-left">
              <InterviewHistory entries={history} fields={fields} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
