/**
 * KB assisted-creation session lifecycle extracted from
 * KBAssistedCreationController (RULE-04 / AUFG-03-04).
 *
 * Owns: session creation on mount, session fetching, abandon-with-resume
 * flow (saves pending interview before abandoning so the user can resume
 * later), and the resume-persistence toggle. Coordinated with the
 * interview-resume persistence helpers (clearPendingInterview etc.).
 */

import type { useTranslations } from "next-intl";
import { type MutableRefObject, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { mapSSEError } from "@/lib/api/ai-error-mapping";
import {
  clearPendingInterview,
  isInterviewResumePersistenceDisabled,
  savePendingInterview,
  setInterviewResumePersistenceDisabled,
} from "@/lib/hooks/use-kb-interview-resume";
import {
  useAbandonKBSession,
  useCompleteKBSession,
  useCreateKBSession,
  useKBSession,
} from "@/lib/hooks/useKBSessions";

export type StudioTranslator = ReturnType<typeof useTranslations>;

interface UseKBAssistedSessionParams {
  novelId: string;
  entityType: import("@/lib/api/kb").KBEntityType;
  resumeSessionId?: string | null;
  entryName: string;
  onComplete: (entryId: string) => void;
  onCancel: () => void;
  t: StudioTranslator;
}

interface UseKBAssistedSessionResult {
  sessionId: string | null;
  setSessionId: (id: string | null) => void;
  session: ReturnType<typeof useKBSession>["data"];
  isLoading: boolean;
  isError: boolean;
  errorMessage: string | undefined;
  completePending: boolean;
  initializedSessionId: MutableRefObject<string | null>;
  createSessionMutation: ReturnType<typeof useCreateKBSession>;
  completeSessionMutation: ReturnType<typeof useCompleteKBSession>;
  abandonSessionMutation: ReturnType<typeof useAbandonKBSession>;
  resumePersistenceEnabled: boolean;
  abandonWithCurrentSession: () => void;
  handleCompleteAndSave: () => void;
  handleResumePersistenceChange: (enabled: boolean) => void;
}

export function useKBAssistedSession({
  novelId,
  entityType,
  resumeSessionId,
  entryName,
  onComplete,
  onCancel,
  t,
}: UseKBAssistedSessionParams): UseKBAssistedSessionResult {
  const [sessionId, setSessionId] = useState<string | null>(resumeSessionId ?? null);
  const [resumePersistenceEnabled, setResumePersistenceEnabled] = useState(
    () => !isInterviewResumePersistenceDisabled(),
  );
  const initializedSessionId = useRef<string | null>(null);

  const createSessionMutation = useCreateKBSession(novelId);
  const completeSessionMutation = useCompleteKBSession(novelId, sessionId ?? "");
  const abandonSessionMutation = useAbandonKBSession(novelId, sessionId ?? "");
  const { data: session, isLoading: sessionLoading } = useKBSession(novelId, sessionId);

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

  function abandonWithCurrentSession() {
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

  function handleCompleteAndSave() {
    if (!sessionId || !entryName.trim()) return;
    // F9-1: the collected entry name travels in the complete body so the
    // backend can fill the session's name before mapping the entry.
    completeSessionMutation.mutate(entryName.trim(), {
      onSuccess: (response) => {
        clearPendingInterview(novelId);
        toast.success(t("kb.sessionSaved"));
        onComplete(response.entry_id);
      },
    });
  }

  function handleResumePersistenceChange(enabled: boolean) {
    setResumePersistenceEnabled(enabled);
    setInterviewResumePersistenceDisabled(!enabled);
    if (!enabled) clearPendingInterview(novelId);
  }

  return {
    sessionId,
    setSessionId,
    session,
    isLoading: createSessionMutation.isPending || sessionLoading,
    isError: createSessionMutation.isError,
    errorMessage: createSessionMutation.error
      ? (mapSSEError(createSessionMutation.error)?.userMessage ?? t("kb.sessionCreateFailed"))
      : undefined,
    completePending: completeSessionMutation.isPending,
    initializedSessionId,
    createSessionMutation,
    completeSessionMutation,
    abandonSessionMutation,
    resumePersistenceEnabled,
    abandonWithCurrentSession,
    handleCompleteAndSave,
    handleResumePersistenceChange,
  };
}
