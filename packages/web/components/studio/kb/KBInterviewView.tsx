"use client";

/**
 * KB Interview View — AI-guided Q&A for KB entry creation.
 *
 * The AI asks questions about the entity, user answers, and the
 * AI extracts relevant field values from the answers.
 */

import { ArrowLeft, Loader2, MessageSquare, Send, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import type { KBCreationSession, KBInterviewResult } from "@/lib/api/kb-sessions";

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
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border bg-card">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            className="p-1.5 text-muted-foreground hover:text-foreground rounded-md hover:bg-muted transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-purple-500" />
            <h3 className="font-medium">{t("kb.interviewMode") || "Interview Mode"}</h3>
          </div>
        </div>
        <div className="text-sm text-muted-foreground">
          {t("kb.interviewProgress", { current: questionCount }) || `Question ${questionCount}`}
        </div>
      </div>

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
            <div className="p-4 border border-red-200 dark:border-red-900/50 rounded-lg bg-red-50 dark:bg-red-950/20">
              <div className="flex items-center justify-between">
                <p className="text-sm text-red-600 dark:text-red-400">
                  {error.message || "Failed to get question"}
                </p>
                <button
                  type="button"
                  onClick={requestNextQuestion}
                  className="flex items-center gap-1 text-xs text-red-600 dark:text-red-400 hover:text-red-700"
                >
                  {t("kb.retry") || "Retry"}
                </button>
              </div>
            </div>
          )}

          {/* Question state */}
          {(state === "question" || state === "answering") && currentQuestion && (
            <div className="space-y-6">
              {/* AI Question */}
              <div className="flex gap-3">
                <div className="w-8 h-8 rounded-full bg-purple-100 dark:bg-purple-900/50 flex items-center justify-center flex-shrink-0">
                  <MessageSquare className="w-4 h-4 text-purple-600 dark:text-purple-400" />
                </div>
                <div className="flex-1 p-4 bg-purple-50 dark:bg-purple-950/20 rounded-lg rounded-tl-none">
                  <p className="text-sm whitespace-pre-wrap">{currentQuestion.question}</p>
                  {currentQuestion.target_field && (
                    <p className="text-xs text-muted-foreground mt-2">
                      {t("kb.aboutField") || "About:"}{" "}
                      {session.fields.find((f) => f.field_key === currentQuestion.target_field)
                        ?.label || currentQuestion.target_field}
                    </p>
                  )}
                </div>
              </div>

              {/* Answer input */}
              <div className="flex gap-3">
                <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/50 flex items-center justify-center flex-shrink-0">
                  <span className="text-xs font-medium text-blue-600 dark:text-blue-400">
                    {t("kb.youLabel") || "You"}
                  </span>
                </div>
                <div className="flex-1 space-y-3">
                  <textarea
                    ref={answerRef}
                    value={answer}
                    onChange={(e) => setAnswer(e.target.value)}
                    placeholder={t("kb.yourAnswer") || "Type your answer..."}
                    className="w-full px-4 py-3 bg-input-background border border-border rounded-lg text-sm min-h-[120px] resize-y focus:outline-none focus:ring-2 focus:ring-primary/50"
                    disabled={state === "answering"}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                        void handleSubmitAnswer();
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
                      onClick={handleSubmitAnswer}
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
          )}

          {/* Complete state */}
          {state === "complete" && (
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
                  onClick={requestNextQuestion}
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
          )}
        </div>
      </div>
    </div>
  );
}
