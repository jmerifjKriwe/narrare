"use client";

/**
 * InterviewQuestionCard — AI question bubble and answer input for interview mode.
 *
 * Extracted from KBInterviewView for RULE-04 compliance.
 */

import { Loader2, MessageSquare, Send, X } from "lucide-react";
import { useTranslations } from "next-intl";
import type { RefObject } from "react";
import type { KBCreationSession, KBInterviewResult } from "@/lib/api/kb-sessions";

interface InterviewQuestionCardProps {
  question: KBInterviewResult;
  session: KBCreationSession;
  answer: string;
  state: "question" | "answering";
  answerRef: RefObject<HTMLTextAreaElement | null>;
  onAnswerChange: (value: string) => void;
  onSubmitAnswer: () => void;
  onBack: () => void;
}

export function InterviewQuestionCard({
  question,
  session,
  answer,
  state,
  answerRef,
  onAnswerChange,
  onSubmitAnswer,
  onBack,
}: InterviewQuestionCardProps) {
  const t = useTranslations("studio");

  return (
    <div className="space-y-6">
      {/* AI Question */}
      <div className="flex gap-3">
        <div className="w-8 h-8 rounded-full bg-purple-100 dark:bg-purple-900/50 flex items-center justify-center flex-shrink-0">
          <MessageSquare className="w-4 h-4 text-purple-600 dark:text-purple-400" />
        </div>
        <div className="flex-1 p-4 bg-purple-50 dark:bg-purple-950/20 rounded-lg rounded-tl-none">
          <p className="text-sm whitespace-pre-wrap">{question.question}</p>
          {question.target_field && (
            <p className="text-xs text-muted-foreground mt-2">
              {t("kb.aboutField")}{" "}
              {session.fields.find((f) => f.field_key === question.target_field)?.label ||
                question.target_field}
            </p>
          )}
        </div>
      </div>

      {/* Answer input */}
      <div className="flex gap-3">
        <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/50 flex items-center justify-center flex-shrink-0">
          <span className="text-xs font-medium text-blue-600 dark:text-blue-400">
            {t("kb.youLabel")}
          </span>
        </div>
        <div className="flex-1 space-y-3">
          <textarea
            ref={answerRef}
            value={answer}
            onChange={(e) => onAnswerChange(e.target.value)}
            placeholder={t("kb.yourAnswer")}
            className="w-full px-4 py-3 bg-input-background border border-border rounded-lg text-sm min-h-[120px] resize-y focus:outline-none focus:ring-2 focus:ring-primary/50"
            disabled={state === "answering"}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                void onSubmitAnswer();
              }
            }}
          />
          <div className="flex justify-between items-center">
            <button
              type="button"
              onClick={onBack}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
              <X className="w-3 h-3" />
              {t("kb.exitInterview")}
            </button>
            <button
              type="button"
              onClick={onSubmitAnswer}
              disabled={!answer.trim() || state === "answering"}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity disabled:opacity-50 text-sm"
            >
              {state === "answering" ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
              {t("kb.submitAnswer")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
