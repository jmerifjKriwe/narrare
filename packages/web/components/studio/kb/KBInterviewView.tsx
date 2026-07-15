"use client";

/**
 * KB Interview View — AI-guided Q&A for KB entry creation.
 *
 * The AI asks questions about the entity, user answers, and the
 * AI extracts relevant field values from the answers.
 *
 * Uses useAIOperation for lifecycle management (§16).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { KBCreationSession, KBInterviewResult } from "@/lib/api/kb-sessions";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import { useInterviewHistory } from "@/lib/hooks/use-interview-history";
import { InterviewCompleteState } from "./InterviewCompleteState";
import { InterviewErrorState } from "./InterviewErrorState";
import { InterviewHeader } from "./InterviewHeader";
import { InterviewLoadingState } from "./InterviewLoadingState";
import { InterviewProgressBar } from "./InterviewProgressBar";
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
  const [phase, setPhase] = useState<InterviewPhase>("idle");
  const [currentQuestion, setCurrentQuestion] = useState<KBInterviewResult | null>(null);
  const [answer, setAnswer] = useState("");
  const [questionCount, setQuestionCount] = useState(0);
  const answerRef = useRef<HTMLTextAreaElement>(null);

  // Accumulate Q&A pairs for post-completion review (searchable history)
  const { entries: history, addEntry } = useInterviewHistory();

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

    const trimmedAnswer = answer.trim();
    setPhase("answering");

    try {
      // If we have a target field, answer it directly
      if (currentQuestion.target_field) {
        await onSubmitAnswer(currentQuestion.target_field, trimmedAnswer);
      }

      // Record the Q&A pair for post-completion review before resetting
      addEntry({
        question: currentQuestion.question,
        answer: trimmedAnswer,
        fieldKey: currentQuestion.target_field,
      });

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

  // Escape-Cancel Handler (KEYBOARD-001)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isLoading) {
        e.preventDefault();
        interviewOp.cancel();
      }
      if (e.key === "Escape" && !isLoading) {
        e.preventDefault();
        onBack();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isLoading, interviewOp.cancel, onBack]);

  return (
    <div className="flex flex-col h-full">
      <InterviewHeader questionCount={questionCount} onBack={onBack} />

      <InterviewProgressBar
        filledFields={session.fields.filter((f) => f.final_value || f.user_value).length}
        totalFields={session.fields.length}
      />

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto space-y-6">
          {/* Loading & connection-lost states */}
          <InterviewLoadingState
            isLoading={isLoading}
            isConnectionLost={interviewOp.isConnectionLost}
            onCancel={interviewOp.cancel}
            onRetry={interviewOp.retry}
          />

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
            <InterviewCompleteState
              onRequestMoreQuestions={requestNextQuestion}
              onBack={onBack}
              history={history}
              fields={session.fields}
            />
          )}
        </div>
      </div>
    </div>
  );
}
