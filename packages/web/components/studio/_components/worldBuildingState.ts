import { useEffect, useState } from "react";
import type { KBEntityType } from "@/lib/api/kb";
import { clearPendingInterview, getPendingInterview } from "@/lib/hooks/use-kb-interview-resume";
import type { KBMode, KBUrlState } from "../kb/kbUrlState";
import { useWorldBuildingNavigation } from "./worldBuildingNavigation";

export function useWorldBuildingState(novelId: string, initialUrlState: KBUrlState) {
  const [activeType, setActiveType] = useState<KBEntityType | null>(initialUrlState.type);
  const [selectedEntryId, setSelectedEntryId] = useState<string | null>(initialUrlState.entryId);
  const [isCreating, setIsCreating] = useState(initialUrlState.mode === "create");
  const [isAssistedSession, setIsAssistedSession] = useState(initialUrlState.mode === "assist");
  const [assistedEntityType, setAssistedEntityType] = useState<KBEntityType | null>(
    initialUrlState.mode === "assist" ? (initialUrlState.type ?? "character") : null,
  );
  const [mode, setMode] = useState<KBMode>(initialUrlState.mode);
  const [resumeSessionId, setResumeSessionId] = useState<string | null>(null);
  const [showResumeDialog, setShowResumeDialog] = useState(false);

  useEffect(() => {
    setActiveType(initialUrlState.type);
    setSelectedEntryId(initialUrlState.entryId);
    setMode(initialUrlState.mode);
    setIsCreating(initialUrlState.mode === "create");
    setIsAssistedSession(initialUrlState.mode === "assist");
    setAssistedEntityType(
      initialUrlState.mode === "assist" ? (initialUrlState.type ?? "character") : null,
    );
    setResumeSessionId(null);
  }, [initialUrlState.entryId, initialUrlState.mode, initialUrlState.type]);

  function resetModes() {
    setMode("detail");
  }

  function resetSelectionForMode() {
    setSelectedEntryId(null);
    setIsCreating(false);
    setIsAssistedSession(false);
  }

  function handleTypeChange(type: KBEntityType | null) {
    setActiveType(type);
    resetSelectionForMode();
    resetModes();
  }

  function handleSelectEntry(entryId: string) {
    setSelectedEntryId(entryId);
    setIsCreating(false);
    setIsAssistedSession(false);
    setMode("detail");
  }

  function handleCreateNew() {
    setIsCreating(true);
    setSelectedEntryId(null);
    setIsAssistedSession(false);
    setMode("create");
  }

  function startNewAssistedSession() {
    clearPendingInterview(novelId);
    setIsAssistedSession(true);
    setAssistedEntityType(activeType ?? "character");
    setResumeSessionId(null);
    setIsCreating(false);
    setSelectedEntryId(null);
    setMode("assist");
  }

  function handleCreateAssisted() {
    if (getPendingInterview(novelId)) setShowResumeDialog(true);
    else startNewAssistedSession();
  }

  function handleResumeInterview() {
    const pending = getPendingInterview(novelId);
    if (pending) {
      setIsAssistedSession(true);
      setAssistedEntityType(pending.entityType as KBEntityType);
      setResumeSessionId(pending.sessionId);
      setIsCreating(false);
      setSelectedEntryId(null);
      setMode("assist");
    }
    setShowResumeDialog(false);
  }

  function handleDiscardResume() {
    clearPendingInterview(novelId);
    setShowResumeDialog(false);
    startNewAssistedSession();
  }

  const navigation = useWorldBuildingNavigation({ mode, setMode, resetSelectionForMode });

  return {
    activeType,
    assistedEntityType,
    handleCreateAssisted,
    handleCreateNew,
    handleDiscardResume,
    handleResumeInterview,
    handleSelectEntry,
    handleTypeChange,
    isAssistedSession,
    isCreating,
    mode,
    resumeSessionId,
    selectedEntryId,
    setMode,
    setShowResumeDialog,
    showResumeDialog,
    ...navigation,
    handleAssistedCancel: () => {
      setIsAssistedSession(false);
      setAssistedEntityType(null);
      setResumeSessionId(null);
      setMode("detail");
    },
    handleAssistedComplete: (entryId: string) => {
      setIsAssistedSession(false);
      setAssistedEntityType(null);
      setResumeSessionId(null);
      setSelectedEntryId(entryId);
      setMode("detail");
    },
    handleCreateCancel: () => {
      setIsCreating(false);
      setMode("detail");
    },
    handleCreated: (entryId: string) => {
      setIsCreating(false);
      setSelectedEntryId(entryId);
      setMode("detail");
    },
    handleDeleted: () => setSelectedEntryId(null),
  };
}
