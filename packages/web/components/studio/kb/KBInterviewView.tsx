"use client";

/**
 * KB Interview View — AI-guided Q&A for KB entry creation.
 *
 * The AI asks questions about the entity, user answers, and the
 * AI extracts relevant field values from the answers.
 *
 * Uses useAIOperation for lifecycle management (§16).
 */

import { Loader2, OctagonX } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import type { KBCreationSession, KBInterviewResult } from "@/lib/api/kb-sessions";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import { InterviewCompleteState } from "./InterviewCompleteState";
import { InterviewErrorState } from "./InterviewErrorState";
import { InterviewHeader } from "./InterviewHeader";
import { InterviewQuestionCard } from "./InterviewQuestionCard";

type InterviewPhase = "idle" | "question" | "answering" | "complete";

interface KBInterviewViewProps {
  novelId: string;
  sessionId: string;
  session: KBCreationSession;
  onRequestQuestion: (signal?: AbortSignal) => Promise<KBInterviewResult>;
  onSubmitAnswer: (fieldKey: string, answer: string) => Promise<void>;
  onBack: () => void;
}

export function KBInterviewView({
  novelId: _novelId,
  sessionId: _sessionId,
  session,
  onRequestQuestion,
  onSubmitAnswer,
  onBack,
}: KBInterviewViewProps) {
  const t = useTranslations("studio");
  const [phase, setPhase] = useState<InterviewPhase>("idle");
  const [currentQuestion, setCurrentQuestion] = useState<KBInterviewResult | null>(null);
  const [answer, setAnswer] = useState("");
  const [questionCount, setQuestionCount] = useState(0);
  const answerRef = useRef<HTMLTextAreaElement>(null);

  // --- AI operation lifecycle via useAIOperation ---
  const interviewOp = useAIOperation<KBInterviewResult>({
    execute: (signal) => onRequestQuestion(signal),
    onSuccess: (result) => {
      setCurrentQuestion(result);
      setQuestionCount((prev) => prev + 1);
      setPhase("question");
      setTimeout(() => answerRef.current?.focus(), 100);
    },
    onError: () => {
      // Error is displayed via interviewOp.state.error — phase stays as-is
    },
  });

  const requestNextQuestion = useCallback(() => {
    setPhase("idle");
    interviewOp.start();
  }, [interviewOp]);

  async function handleSubmitAnswer() {
    if (!currentQuestion || !answer.trim()) return;

    setPhase("answering");

    try {
      // If we have a target field, answer it directly
      if (currentQuestion.target_field) {
        await onSubmitAnswer(currentQuestion.target_field, answer.trim());
      }

      // Reset answer and check if done
      setAnswer("");

      const requiredFields = session.fields.filter((f) => f.required);
      const filledRequired = requiredFields.filter((f) => f.final_value || f.user_value);

      if (filledRequired.length >= requiredFields.length && questionCount >= 3) {
        setPhase("complete");
      } else {
        requestNextQuestion();
      }
    } catch {
      // Answer submission errors are non-AI; stay in answering phase
      // The field mutation handles its own error state
      setPhase("question");
    }
  }

  // Start interview on mount
  // biome-ignore lint/correctness/useExhaustiveDependencies: Runs once on mount — intentional mount-trigger pattern
  useEffect(() => {
    if (phase !== "idle") return;
    interviewOp.start();
  }, []);

  // Derive display state from hook + phase
  const isLoading = interviewOp.isLoading || interviewOp.isStreaming;
  const isError = interviewOp.isError || interviewOp.isConnectionLost;
  const error = interviewOp.state.error;

  // Calculate progress
  const totalFields = session.fields.length;
  const filledFields = session.fields.filter((f) => f.final_value || f.user_value).length;

  return (
    <div className="flex flex-col h-full">
      <InterviewHeader questionCount={questionCount} onBack={onBack} />

      {/* Progress bar */}
      <div className="h-1 bg-muted">
        <div
          className="h-full bg-purple-500 transition-all duration-300"
          style={{ width: totalFields > 0 ? `${(filledFields / totalFields) * 100}%` : "0%" }}
        />
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto space-y-6">
          {/* Loading state */}
          {isLoading && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Loader2 className="w-8 h-8 text-muted-foreground animate-spin mb-4" />
              <p className="text-muted-foreground">{t("aiActions.aiThinking")}</p>
              <button
                type="button"
                onClick={interviewOp.cancel}
                className="flex items-center gap-1.5 mt-4 px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground border border-border rounded-md hover:bg-muted transition-colors"
              >
                <OctagonX className="w-3.5 h-3.5" />
                {t("aiActions.stop")}
              </button>
            </div>
          )}

          {/* Connection lost state */}
          {interviewOp.isConnectionLost && (
            <div className="p-4 border border-amber-200 dark:border-amber-900/50 rounded-lg bg-amber-50 dark:bg-amber-950/20">
              <div className="flex items-center justify-between">
                <p className="text-sm text-amber-600 dark:text-amber-400">
                  {t("aiActions.connectionLost")}
                </p>
                <button
                  type="button"
                  onClick={interviewOp.retry}
                  className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400 hover:text-amber-700"
                >
                  {t("aiActions.connectionLostRetry")}
                </button>
              </div>
            </div>
          )}

          {/* Error state */}
          {isError && !interviewOp.isConnectionLost && error && (
            <InterviewErrorState error={error} onRetry={interviewOp.retry} />
          )}

          {/* Question state */}
          {(phase === "question" || phase === "answering") && currentQuestion && !isLoading && (
            <InterviewQuestionCard
              question={currentQuestion}
              session={session}
              answer={answer}
              state={phase}
              answerRef={answerRef}
              onAnswerChange={setAnswer}
              onSubmitAnswer={handleSubmitAnswer}
              onBack={onBack}
            />
          )}

          {/* Complete state */}
          {phase === "complete" && (
            <InterviewCompleteState onRequestMoreQuestions={requestNextQuestion} onBack={onBack} />
          )}
        </div>
      </div>
    </div>
  );
}
