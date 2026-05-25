"use client";

/**
 * KB Assisted Creation Panel — Main container for AI-assisted KB entry creation.
 *
 * Orchestrates the session lifecycle and routes between sub-views:
 * - Field list view (default)
 * - Interview view
 * - Enhance review view
 *
 * Follows RULE-06 (one responsibility): this component only manages
 * view state and session lifecycle — actual field rendering and
 * interaction logic delegated to sub-components.
 */

import { Sparkles, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import type { KBEntityType } from "@/lib/api/kb";
import type { KBEnhancementResult, KBInterviewResult } from "@/lib/api/kb-sessions";
import {
  useAbandonKBSession,
  useAnswerField,
  useCompleteKBSession,
  useCreateKBSession,
  useKBSession,
  useKBSessionEnhance,
  useKBSessionInterview,
  useKBSessionSuggest,
} from "@/lib/hooks/useKBSessions";
import { TYPE_ICONS } from "./constants";
import { KBAssistedCreationFooter } from "./KBAssistedCreationFooter";
import { KBEnhanceReview } from "./KBEnhanceReview";
import { KBInterviewView } from "./KBInterviewView";
import { KBSessionFieldList } from "./KBSessionFieldList";

export type AssistedView = "fields" | "interview" | "enhance";

interface KBAssistedCreationPanelProps {
  novelId: string;
  entityType: KBEntityType;
  onComplete: (entryId: string) => void;
  onCancel: () => void;
}

export function KBAssistedCreationPanel({
  novelId,
  entityType,
  onComplete,
  onCancel,
}: KBAssistedCreationPanelProps) {
  const t = useTranslations("studio");
  const [view, setView] = useState<AssistedView>("fields");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [suggestingFieldKey, setSuggestingFieldKey] = useState<string | null>(null);
  const [confirmAbandon, setConfirmAbandon] = useState(false);
  const [entryName, setEntryName] = useState("");

  // --- Session mutations ---
  const createSessionMutation = useCreateKBSession(novelId);
  const answerFieldMutation = useAnswerField(novelId, sessionId ?? "");
  const completeSessionMutation = useCompleteKBSession(novelId, sessionId ?? "");
  const abandonSessionMutation = useAbandonKBSession(novelId, sessionId ?? "");

  // --- AI operations (SSE-based) ---
  const suggestMutation = useKBSessionSuggest(novelId, sessionId ?? "");
  const interviewMutation = useKBSessionInterview(novelId, sessionId ?? "");
  const enhanceMutation = useKBSessionEnhance(novelId, sessionId ?? "");

  // --- Session query ---
  const { data: session, isLoading: sessionLoading } = useKBSession(novelId, sessionId);

  // --- Create session on mount ---
  useEffect(() => {
    if (!sessionId && !createSessionMutation.isPending) {
      createSessionMutation.mutate(entityType, {
        onSuccess: (newSession) => {
          setSessionId(newSession.id);
        },
      });
    }
  }, [entityType, sessionId, createSessionMutation]);

  // --- Reset entry name when a new session is loaded ---
  // Use ref to track which session we've initialized the name for,
  // so we don't overwrite user input when session updates poll.
  const initializedSessionId = useRef<string | null>(null);

  useEffect(() => {
    if (session && session.id !== initializedSessionId.current) {
      setEntryName(session.name || "");
      initializedSessionId.current = session.id;
    }
  }, [session]);

  // --- Calculate progress ---
  const totalFields = session?.fields.length ?? 0;
  const filledFields =
    session?.fields.filter((f) => f.final_value || f.user_value || f.ai_suggested_value).length ??
    0;

  // --- Event handlers ---

  async function handleSuggest(fieldKey: string) {
    if (!sessionId) return;
    setSuggestingFieldKey(fieldKey);
    suggestMutation.mutate(
      { fieldKey },
      {
        onSettled: () => setSuggestingFieldKey(null),
      },
    );
  }

  function handleAnswer(fieldKey: string, value: string) {
    if (!sessionId) return;
    answerFieldMutation.mutate({ fieldKey, value });
  }

  function handleAcceptSuggestion(fieldKey: string, value: string) {
    // Accepting a suggestion is just answering the field with the suggested value
    handleAnswer(fieldKey, value);
  }

  function handleRejectSuggestion(_fieldKey: string) {
    // Rejection currently just dismisses — could clear ai_suggested_value in future
    // For now, do nothing as the user can just edit the field
  }

  async function handleRequestInterview(signal?: AbortSignal): Promise<KBInterviewResult> {
    if (!sessionId) {
      throw new Error("No active session");
    }
    return new Promise((resolve, reject) => {
      interviewMutation.mutate(signal, {
        onSuccess: resolve,
        onError: reject,
      });
    });
  }

  async function handleSubmitInterviewAnswer(fieldKey: string, answer: string) {
    handleAnswer(fieldKey, answer);
  }

  async function handleRequestEnhance(): Promise<KBEnhancementResult[]> {
    if (!sessionId) {
      throw new Error("No active session");
    }
    return new Promise((resolve, reject) => {
      enhanceMutation.mutate(undefined, {
        onSuccess: resolve,
        onError: reject,
      });
    });
  }

  function handleAcceptEnhancement(fieldKey: string, value: string) {
    handleAnswer(fieldKey, value);
  }

  function handleApplySelectedEnhancements() {
    setView("fields");
  }

  function handleCompleteAndSave() {
    if (!sessionId) return;
    if (!entryName.trim()) return;

    completeSessionMutation.mutate(undefined, {
      onSuccess: (response) => {
        onComplete(response.entry_id);
      },
    });
  }

  function handleAbandon() {
    if (!confirmAbandon) {
      setConfirmAbandon(true);
      return;
    }

    if (sessionId) {
      abandonSessionMutation.mutate(undefined, {
        onSuccess: onCancel,
      });
    } else {
      onCancel();
    }
  }

  // --- Get icon for entity type ---
  const EntityIcon = TYPE_ICONS[entityType] || Sparkles;

  // --- Loading state ---
  if (createSessionMutation.isPending || sessionLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-background">
        <div className="text-center">
          <EntityIcon className="w-12 h-12 mx-auto mb-4 text-muted-foreground opacity-50 animate-pulse" />
          <p className="text-muted-foreground">
            {t("kb.creatingSession") || "Creating session..."}
          </p>
        </div>
      </div>
    );
  }

  // --- Error state ---
  if (createSessionMutation.isError || !session) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-background">
        <div className="text-center max-w-md">
          <p className="text-red-500 mb-4">
            {createSessionMutation.error?.message ||
              t("kb.sessionCreateFailed") ||
              "Failed to create session"}
          </p>
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 border border-border rounded-md hover:bg-muted transition-colors text-sm"
          >
            {t("kb.cancel")}
          </button>
        </div>
      </div>
    );
  }

  // --- Interview view ---
  if (view === "interview") {
    return (
      <KBInterviewView
        novelId={novelId}
        sessionId={sessionId ?? ""}
        session={session}
        onRequestQuestion={handleRequestInterview}
        onSubmitAnswer={handleSubmitInterviewAnswer}
        onBack={() => setView("fields")}
      />
    );
  }

  // --- Enhance review view ---
  if (view === "enhance") {
    return (
      <KBEnhanceReview
        session={session}
        onRequestEnhance={handleRequestEnhance}
        onAcceptEnhancement={handleAcceptEnhancement}
        onApplySelected={handleApplySelectedEnhancements}
        onBack={() => setView("fields")}
      />
    );
  }

  // --- Main: Field list view ---
  return (
    <div className="flex-1 flex flex-col bg-background">
      {/* Header */}
      <div className="border-b border-border bg-card p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-purple-600 dark:text-purple-400" />
            </div>
            <div>
              <h2 className="font-medium">
                {t("kb.aiAssistedCreation") || "AI-Assisted Creation"}
              </h2>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <EntityIcon className="w-3.5 h-3.5" />
                <span>{t(`kb.${entityType}s`) || entityType}</span>
                <span className="text-xs px-2 py-0.5 rounded bg-muted">
                  {session.status === "active"
                    ? t("kb.statusActive") || "Active"
                    : session.status === "review"
                      ? t("kb.statusReview") || "Review"
                      : session.status}
                </span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Confirm abandon dialog */}
            {confirmAbandon ? (
              <div className="flex items-center gap-2 text-sm">
                <span className="text-red-500">{t("kb.confirmAbandon")}</span>
                <button
                  type="button"
                  onClick={() => setConfirmAbandon(false)}
                  className="px-3 py-1.5 border border-border rounded-md hover:bg-muted transition-colors text-xs"
                >
                  {t("kb.cancel")}
                </button>
                <button
                  type="button"
                  onClick={handleAbandon}
                  disabled={abandonSessionMutation.isPending}
                  className="flex items-center gap-1 px-3 py-1.5 bg-red-500 text-white rounded-md hover:bg-red-600 transition-colors text-xs disabled:opacity-50"
                >
                  {abandonSessionMutation.isPending ? (
                    t("kb.abandoning") || "Abandoning..."
                  ) : (
                    <>
                      <Trash2 className="w-3 h-3" />
                      {t("kb.confirm") || "Confirm"}
                    </>
                  )}
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={handleAbandon}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground rounded-md hover:bg-muted transition-colors"
              >
                <Trash2 className="w-4 h-4" />
                {t("kb.abandon")}
              </button>
            )}
          </div>
        </div>

        {/* Progress bar */}
        <div className="flex items-center justify-between text-xs text-muted-foreground mb-1.5">
          <span>{t("kb.sessionProgress", { filled: filledFields, total: totalFields })}</span>
          <span>
            {totalFields > 0 ? `${Math.round((filledFields / totalFields) * 100)}%` : "0%"}
          </span>
        </div>
        <div className="h-1.5 bg-muted rounded-full overflow-hidden">
          <div
            className="h-full bg-purple-500 transition-all duration-300"
            style={{ width: totalFields > 0 ? `${(filledFields / totalFields) * 100}%` : "0%" }}
          />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl mx-auto">
          <KBSessionFieldList
            session={session}
            onSuggest={handleSuggest}
            onAnswer={handleAnswer}
            onAcceptSuggestion={handleAcceptSuggestion}
            onRejectSuggestion={handleRejectSuggestion}
            onStartInterview={() => setView("interview")}
            onEnhance={() => setView("enhance")}
            suggestingFieldKey={suggestingFieldKey}
          />
        </div>
      </div>

      {/* Footer: name input + actions */}
      <KBAssistedCreationFooter
        session={session}
        entryName={entryName}
        setEntryName={setEntryName}
        view={view}
        setView={setView}
        filledFields={filledFields}
        completePending={completeSessionMutation.isPending}
        onCancel={onCancel}
        onCompleteAndSave={handleCompleteAndSave}
      />
    </div>
  );
}
