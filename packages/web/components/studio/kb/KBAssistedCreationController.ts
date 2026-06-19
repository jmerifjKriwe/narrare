import type { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { mapSSEError } from "@/lib/api/ai-error-mapping";
import type { KBEntityType } from "@/lib/api/kb";
import type {
  KBEnhancementResult,
  KBInterviewResult,
  KBSuggestionResult,
} from "@/lib/api/kb-sessions";
import { type AIErrorResponse, useAIOperation } from "@/lib/hooks/use-ai-operation";
import {
  clearPendingInterview,
  isInterviewResumePersistenceDisabled,
  savePendingInterview,
  setInterviewResumePersistenceDisabled,
} from "@/lib/hooks/use-kb-interview-resume";
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
import type { AssistedView } from "./KBAssistedCreationPanel";

type StudioTranslator = ReturnType<typeof useTranslations>;

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
  const [sessionId, setSessionId] = useState<string | null>(resumeSessionId ?? null);
  const [suggestingFieldKey, setSuggestingFieldKey] = useState<string | null>(null);
  const [suggestionError, setSuggestionError] = useState<AIErrorResponse | null>(null);
  const [suggestionErrorFieldKey, setSuggestionErrorFieldKey] = useState<string | null>(null);
  const [confirmAbandon, setConfirmAbandon] = useState(false);
  const [entryName, setEntryName] = useState("");
  const [resumePersistenceEnabled, setResumePersistenceEnabled] = useState(
    () => !isInterviewResumePersistenceDisabled(),
  );
  const initializedSessionId = useRef<string | null>(null);
  const pendingSuggestFieldKey = useRef<string | null>(null);

  const createSessionMutation = useCreateKBSession(novelId);
  const answerFieldMutation = useAnswerField(novelId, sessionId ?? "");
  const completeSessionMutation = useCompleteKBSession(novelId, sessionId ?? "");
  const abandonSessionMutation = useAbandonKBSession(novelId, sessionId ?? "");
  const suggestMutation = useKBSessionSuggest(novelId, sessionId ?? "");
  const interviewMutation = useKBSessionInterview(novelId, sessionId ?? "");
  const enhanceMutation = useKBSessionEnhance(novelId, sessionId ?? "");
  const { data: session, isLoading: sessionLoading } = useKBSession(novelId, sessionId);

  const suggestOp = useAIOperation<KBSuggestionResult>({
    execute: async (signal) => {
      const fieldKey = pendingSuggestFieldKey.current;
      if (!sessionId || !fieldKey) throw new Error("No active field suggestion");
      return suggestMutation.mutateAsync({ fieldKey, signal });
    },
    errorMapper: mapSSEError,
    onSuccess: () => {
      pendingSuggestFieldKey.current = null;
      setSuggestingFieldKey(null);
      setSuggestionError(null);
      setSuggestionErrorFieldKey(null);
    },
    onError: (error) => {
      const fieldKey = pendingSuggestFieldKey.current;
      pendingSuggestFieldKey.current = null;
      setSuggestingFieldKey(null);
      setSuggestionError(error);
      setSuggestionErrorFieldKey(fieldKey);
    },
  });

  useEffect(() => {
    if (!sessionId && !createSessionMutation.isPending) {
      createSessionMutation.mutate(entityType, {
        onSuccess: (newSession) => setSessionId(newSession.id),
      });
    }
  }, [entityType, sessionId, createSessionMutation]);

  useEffect(() => {
    return () => {
      if (sessionId) clearPendingInterview(novelId);
    };
  }, [novelId, sessionId]);

  useEffect(() => {
    if (session && session.id !== initializedSessionId.current) {
      setEntryName(session.name || "");
      initializedSessionId.current = session.id;
    }
  }, [session]);

  const totalFields = session?.fields.length ?? 0;
  const filledFields =
    session?.fields.filter(
      (field) => field.final_value || field.user_value || field.ai_suggested_value,
    ).length ?? 0;

  function handleAnswer(fieldKey: string, value: string): void {
    if (!sessionId) return;
    answerFieldMutation.mutate({ fieldKey, value });
  }

  function handleSuggest(fieldKey: string): void {
    if (!sessionId) return;
    setSuggestionError(null);
    setSuggestionErrorFieldKey(null);
    setSuggestingFieldKey(fieldKey);
    pendingSuggestFieldKey.current = fieldKey;
    suggestOp.start();
  }

  function handleCancelSuggest(): void {
    suggestOp.cancel();
    pendingSuggestFieldKey.current = null;
    setSuggestingFieldKey(null);
  }

  function handleAcceptSuggestion(fieldKey: string, value: string): void {
    handleAnswer(fieldKey, value);
  }

  function handleRejectSuggestion(_fieldKey: string): void {
    // Rejection only dismisses the suggestion; users can edit the field manually.
  }

  async function handleRequestInterview(signal?: AbortSignal): Promise<KBInterviewResult> {
    if (!sessionId) throw new Error("No active session");
    return new Promise((resolve, reject) => {
      interviewMutation.mutate(signal, { onSuccess: resolve, onError: reject });
    });
  }

  async function handleSubmitInterviewAnswer(fieldKey: string, answer: string): Promise<void> {
    handleAnswer(fieldKey, answer);
  }

  async function handleRequestEnhance(signal?: AbortSignal): Promise<KBEnhancementResult[]> {
    if (!sessionId) throw new Error("No active session");
    return new Promise((resolve, reject) => {
      enhanceMutation.mutate(signal, { onSuccess: resolve, onError: reject });
    });
  }

  function abandonWithCurrentSession(): void {
    if (!sessionId) {
      onCancel();
      return;
    }
    savePendingInterview(novelId, sessionId, entityType);
    abandonSessionMutation.mutate(undefined, {
      onSuccess: () => {
        toast.success(
          resumePersistenceEnabled ? t("kb.sessionAbandoned") : t("kb.sessionAbandonedWithoutSave"),
        );
        onCancel();
      },
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
    isLoading: createSessionMutation.isPending || sessionLoading,
    isError: createSessionMutation.isError,
    errorMessage: createSessionMutation.error
      ? (mapSSEError(createSessionMutation.error)?.userMessage ?? t("kb.sessionCreateFailed"))
      : undefined,
    completePending: completeSessionMutation.isPending,
    handleSuggest,
    handleCancelSuggest,
    suggestionError,
    suggestionErrorFieldKey,
    handleAnswer,
    handleAcceptSuggestion,
    handleRejectSuggestion,
    handleRequestInterview,
    handleSubmitInterviewAnswer,
    handleRequestEnhance,
    handleAcceptEnhancement: handleAnswer,
    handleApplySelectedEnhancements: () => setView("fields"),
    handleCompleteAndSave: () => {
      if (!sessionId || !entryName.trim()) return;
      completeSessionMutation.mutate(undefined, {
        onSuccess: (response) => {
          clearPendingInterview(novelId);
          toast.success(t("kb.sessionSaved"));
          onComplete(response.entry_id);
        },
      });
    },
    handleAbandon: () => {
      if (!confirmAbandon) setConfirmAbandon(true);
      else abandonWithCurrentSession();
    },
    handleConfirmAbandon: abandonWithCurrentSession,
    handleResumePersistenceChange: (enabled: boolean) => {
      setResumePersistenceEnabled(enabled);
      setInterviewResumePersistenceDisabled(!enabled);
      if (!enabled) clearPendingInterview(novelId);
    },
  };
}
