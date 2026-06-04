"use client";

/**
 * KB Interview View — AI-guided Q&A for KB entry creation.
 *
 * The AI asks questions about the entity, user answers, and the
 * AI extracts relevant field values from the answers.
 */

import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import type { KBCreationSession, KBInterviewResult } from "@/lib/api/kb-sessions";
import { InterviewCompleteState } from "./InterviewCompleteState";
import { InterviewErrorState } from "./InterviewErrorState";
import { InterviewHeader } from "./InterviewHeader";
import { InterviewQuestionCard } from "./InterviewQuestionCard";

type InterviewState = "idle" | "loading" | "question" | "answering" | "complete" | "error";

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
  const [state, setState] = useState<InterviewState>("idle");
  const [currentQuestion, setCurrentQuestion] = useState<KBInterviewResult | null>(null);
  const [answer, setAnswer] = useState("");
  const [questionCount, setQuestionCount] = useState(0);
  const [error, setError] = useState<Error | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const answerRef = useRef<HTMLTextAreaElement>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  // Calculate progress
  const totalFields = session.fields.length;
  const filledFields = session.fields.filter((f) => f.final_value || f.user_value).length;

  async function requestNextQuestion() {
    // Abort any in-flight request
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setState("loading");
    setError(null);

    try {
      const result = await onRequestQuestion(controller.signal);
      setCurrentQuestion(result);
      setQuestionCount((prev) => prev + 1);
      setState("question");

      // Focus answer input after a short delay
      setTimeout(() => {
        answerRef.current?.focus();
      }, 100);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }
      setError(err instanceof Error ? err : new Error(String(err)));
      setState("error");
    }
  }

  async function handleSubmitAnswer() {
    if (!currentQuestion || !answer.trim()) return;

    setState("answering");

    try {
      // If we have a target field, answer it directly
      if (currentQuestion.target_field) {
        await onSubmitAnswer(currentQuestion.target_field, answer.trim());
      }

      // Reset answer and request next question
      setAnswer("");

      // Check if we're done (all required fields filled)
      const requiredFields = session.fields.filter((f) => f.required);
      const filledRequired = requiredFields.filter((f) => f.final_value || f.user_value);

      if (filledRequired.length >= requiredFields.length && questionCount >= 3) {
        setState("complete");
      } else {
        await requestNextQuestion();
      }
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      setState("error");
    }
  }

  // biome-ignore lint/correctness/useExhaustiveDependencies: Runs once on mount — intentional mount-trigger pattern
  useEffect(() => {
    if (state !== "idle") return;

    const startInterview = async () => {
      abortControllerRef.current?.abort();
      const controller = new AbortController();
      abortControllerRef.current = controller;

      setState("loading");
      try {
        const result = await onRequestQuestion(controller.signal);
        setCurrentQuestion(result);
        setQuestionCount((prev) => prev + 1);
        setState("question");
        setTimeout(() => answerRef.current?.focus(), 100);
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err instanceof Error ? err : new Error(String(err)));
        setState("error");
      }
    };
    void startInterview();
  }, []);

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
          {state === "loading" && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Loader2 className="w-8 h-8 text-muted-foreground animate-spin mb-4" />
              <p className="text-muted-foreground">{t("kb.aiThinking")}</p>
            </div>
          )}

          {/* Error state */}
          {state === "error" && error && (
            <InterviewErrorState error={error} onRetry={requestNextQuestion} />
          )}

          {/* Question state */}
          {(state === "question" || state === "answering") && currentQuestion && (
            <InterviewQuestionCard
              question={currentQuestion}
              session={session}
              answer={answer}
              state={state}
              answerRef={answerRef}
              onAnswerChange={setAnswer}
              onSubmitAnswer={handleSubmitAnswer}
              onBack={onBack}
            />
          )}

          {/* Complete state */}
          {state === "complete" && (
            <InterviewCompleteState onRequestMoreQuestions={requestNextQuestion} onBack={onBack} />
          )}
        </div>
      </div>
    </div>
  );
}
