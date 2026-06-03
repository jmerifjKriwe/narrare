import { useState } from "react";
import type { KBEntityType } from "@/lib/api/kb";
import { clearPendingInterview, getPendingInterview } from "@/lib/hooks/use-kb-interview-resume";

export function useWorldBuildingState(novelId: string) {
  const [activeType, setActiveType] = useState<KBEntityType | null>(null);
  const [selectedEntryId, setSelectedEntryId] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isAssistedSession, setIsAssistedSession] = useState(false);
  const [assistedEntityType, setAssistedEntityType] = useState<KBEntityType | null>(null);
  const [resumeSessionId, setResumeSessionId] = useState<string | null>(null);
  const [showResumeDialog, setShowResumeDialog] = useState(false);
  const [showAnalysis, setShowAnalysis] = useState(false);
  const [showConsistency, setShowConsistency] = useState(false);
  const [showGraph, setShowGraph] = useState(false);
  const [showWiki, setShowWiki] = useState(false);

  function resetModes() {
    setShowAnalysis(false);
    setShowConsistency(false);
    setShowGraph(false);
    setShowWiki(false);
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
    setShowAnalysis(false);
    setShowConsistency(false);
  }

  function handleCreateNew() {
    setIsCreating(true);
    setSelectedEntryId(null);
    setIsAssistedSession(false);
    setShowAnalysis(false);
    setShowConsistency(false);
  }

  function startNewAssistedSession() {
    clearPendingInterview(novelId);
    setIsAssistedSession(true);
    setAssistedEntityType(activeType ?? "character");
    setResumeSessionId(null);
    setIsCreating(false);
    setSelectedEntryId(null);
    setShowAnalysis(false);
    setShowConsistency(false);
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
      setShowAnalysis(false);
      setShowConsistency(false);
    }
    setShowResumeDialog(false);
  }

  function handleDiscardResume() {
    clearPendingInterview(novelId);
    setShowResumeDialog(false);
    startNewAssistedSession();
  }

  function handleShowAnalysis() {
    setShowAnalysis(true);
    resetSelectionForMode();
    setShowConsistency(false);
  }

  function handleShowConsistency() {
    setShowConsistency(true);
    resetSelectionForMode();
    setShowAnalysis(false);
  }

  function handleShowGraph() {
    setShowGraph(true);
    resetSelectionForMode();
    setShowAnalysis(false);
    setShowConsistency(false);
    setShowWiki(false);
  }

  function handleShowWiki() {
    setShowWiki(true);
    resetSelectionForMode();
    setShowAnalysis(false);
    setShowConsistency(false);
    setShowGraph(false);
  }

  return {
    activeType,
    assistedEntityType,
    handleCreateAssisted,
    handleCreateNew,
    handleDiscardResume,
    handleResumeInterview,
    handleSelectEntry,
    handleShowAnalysis,
    handleShowConsistency,
    handleShowGraph,
    handleShowWiki,
    handleTypeChange,
    isAssistedSession,
    isCreating,
    resumeSessionId,
    selectedEntryId,
    setShowAnalysis,
    setShowConsistency,
    setShowResumeDialog,
    showAnalysis,
    showConsistency,
    showGraph,
    showResumeDialog,
    showWiki,
    handleAssistedCancel: () => {
      setIsAssistedSession(false);
      setAssistedEntityType(null);
      setResumeSessionId(null);
    },
    handleAssistedComplete: (entryId: string) => {
      setIsAssistedSession(false);
      setAssistedEntityType(null);
      setResumeSessionId(null);
      setSelectedEntryId(entryId);
    },
    handleCloseWiki: () => setShowWiki(false),
    handleCreateCancel: () => setIsCreating(false),
    handleCreated: (entryId: string) => {
      setIsCreating(false);
      setSelectedEntryId(entryId);
    },
    handleDeleted: () => setSelectedEntryId(null),
  };
}
