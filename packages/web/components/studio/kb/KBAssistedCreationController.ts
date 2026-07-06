import { useEffect, useState } from "react";
import type { KBEntityType } from "@/lib/api/kb";
import type { KBEnhancementResult, KBInterviewResult } from "@/lib/api/kb-sessions";
import {
  useAnswerField,
  useKBSessionEnhance,
  useKBSessionInterview,
} from "@/lib/hooks/useKBSessions";
import type { AssistedView } from "./KBAssistedCreationPanel";
import { useKBAssistedSession } from "./useKBAssistedSession";

// Re-export for backwards compatibility (the type now lives in useKBAssistedSession
// to avoid a circular import between controller and the session sub-hook).
export type { StudioTranslator } from "./useKBAssistedSession";

import type { StudioTranslator } from "./useKBAssistedSession";
import { useKBFieldSuggest } from "./useKBFieldSuggest";

interface ControllerParams {
  novelId: string;
  entityType: KBEntityType;
  resumeSessionId?: string | null;
  onComplete: (entryId: string) => void;
  onCancel: () => void;
  t: StudioTranslator;
}

export function useKBAssistedCreationController({
  novelId,
  entityType,
  resumeSessionId,
  onComplete,
  onCancel,
  t,
}: ControllerParams) {
  const [view, setView] = useState<AssistedView>("fields");
  const [confirmAbandon, setConfirmAbandon] = useState(false);
  const [entryName, setEntryName] = useState("");

  const {
    sessionId,
    session,
    isLoading,
    isError,
    errorMessage,
    completePending,
    initializedSessionId,
    resumePersistenceEnabled,
    abandonWithCurrentSession,
    handleCompleteAndSave,
    handleResumePersistenceChange,
  } = useKBAssistedSession({
    novelId,
    entityType,
    resumeSessionId,
    entryName,
    onComplete,
    onCancel,
    t,
  });

  const {
    suggestingFieldKey,
    suggestionError,
    suggestionErrorFieldKey,
    handleSuggest,
    handleCancelSuggest,
  } = useKBFieldSuggest({ novelId, sessionId });

  const answerFieldMutation = useAnswerField(novelId, sessionId ?? "");
  const interviewMutation = useKBSessionInterview(novelId, sessionId ?? "");
  const enhanceMutation = useKBSessionEnhance(novelId, sessionId ?? "");

  useEffect(() => {
    if (session && session.id !== initializedSessionId.current) {
      setEntryName(session.name || "");
      initializedSessionId.current = session.id;
    }
  }, [session, initializedSessionId]);

  const totalFields = session?.fields.length ?? 0;
  const filledFields =
    session?.fields.filter(
      (field) => field.final_value || field.user_value || field.ai_suggested_value,
    ).length ?? 0;

  function handleAnswer(fieldKey: string, value: string): void {
    if (!sessionId) return;
    answerFieldMutation.mutate({ fieldKey, value });
  }

  async function handleRequestInterview(signal?: AbortSignal): Promise<KBInterviewResult> {
    if (!sessionId) throw new Error("No active session");
    return new Promise((resolve, reject) => {
      interviewMutation.mutate(signal, { onSuccess: resolve, onError: reject });
    });
  }

  async function handleRequestEnhance(signal?: AbortSignal): Promise<KBEnhancementResult[]> {
    if (!sessionId) throw new Error("No active session");
    return new Promise((resolve, reject) => {
      enhanceMutation.mutate(signal, { onSuccess: resolve, onError: reject });
    });
  }

  return {
    view,
    setView,
    sessionId,
    session,
    suggestingFieldKey,
    confirmAbandon,
    setConfirmAbandon,
    entryName,
    setEntryName,
    resumePersistenceEnabled,
    totalFields,
    filledFields,
    isLoading,
    isError,
    errorMessage,
    completePending,
    handleSuggest,
    handleCancelSuggest,
    suggestionError,
    suggestionErrorFieldKey,
    handleAnswer,
    handleAcceptSuggestion: (fieldKey: string, value: string) => handleAnswer(fieldKey, value),
    handleRejectSuggestion: (_fieldKey: string) => {
      // Rejection only dismisses the suggestion; users can edit the field manually.
    },
    handleRequestInterview,
    handleSubmitInterviewAnswer: async (fieldKey: string, answer: string) =>
      handleAnswer(fieldKey, answer),
    handleRequestEnhance,
    handleAcceptEnhancement: handleAnswer,
    handleApplySelectedEnhancements: () => setView("fields"),
    handleCompleteAndSave,
    handleAbandon: () => {
      if (!confirmAbandon) setConfirmAbandon(true);
      else abandonWithCurrentSession();
    },
    handleConfirmAbandon: abandonWithCurrentSession,
    handleResumePersistenceChange,
  };
}
