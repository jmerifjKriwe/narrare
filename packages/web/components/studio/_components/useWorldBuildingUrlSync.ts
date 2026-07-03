"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { searchParamsHref } from "@/lib/url-state/searchParams";
import { type KBUrlState, serializeKBUrlState } from "../kb/kbUrlState";
import type { useWorldBuildingState } from "./worldBuildingState";

/**
 * useWorldBuildingUrlSync — synchronizes KB browser URL state.
 *
 * Single responsibility: read the URL into `urlState`-shaped transitions,
 * build hrefs, and push/replace them while coordinating with the local
 * world-building state actions. Extracted from WorldBuilding.tsx (RULE-04).
 */

type WorldBuildingState = ReturnType<typeof useWorldBuildingState>;

export function useWorldBuildingUrlSync(state: WorldBuildingState, urlState: KBUrlState) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const searchParamsSnapshot = searchParams.toString();

  const buildKBHref = (nextState: KBUrlState) => {
    const nextParams = new URLSearchParams(searchParamsSnapshot);
    nextParams.delete("type");
    nextParams.delete("mode");
    nextParams.delete("entry");
    nextParams.delete("q");
    const serializedState = serializeKBUrlState(nextState);
    serializedState.forEach((value, key) => {
      nextParams.set(key, value);
    });
    return searchParamsHref(pathname, nextParams);
  };

  const pushKBState = (nextState: KBUrlState) => {
    router.push(buildKBHref(nextState), { scroll: false });
  };

  const replaceKBState = (nextState: KBUrlState) => {
    router.replace(buildKBHref(nextState), { scroll: false });
  };

  const handleTypeChange = (type: KBUrlState["type"]) => {
    state.handleTypeChange(type);
    pushKBState({ type, mode: "detail", entryId: null, query: urlState.query });
  };

  const handleSelectEntry = (entryId: string) => {
    state.handleSelectEntry(entryId);
    pushKBState({ ...urlState, mode: "detail", entryId });
  };

  const handleCreateNew = () => {
    state.handleCreateNew();
    pushKBState({ ...urlState, mode: "create", entryId: null });
  };

  const handleCreateAssisted = () => {
    state.handleCreateAssisted();
    pushKBState({ ...urlState, mode: "assist", entryId: null });
  };

  const handleAnalyze = () => {
    state.handleShowAnalysis();
    pushKBState({ ...urlState, mode: "analysis" });
  };

  const handleConsistencyCheck = () => {
    state.handleShowConsistency();
    pushKBState({ ...urlState, mode: "consistency" });
  };

  const handleShowGraph = () => {
    state.handleShowGraph();
    pushKBState({ ...urlState, mode: "graph" });
  };

  const handleShowWiki = () => {
    state.handleShowWiki();
    pushKBState({ ...urlState, mode: "wiki" });
  };

  const handleSearchQueryChange = (query: string) => {
    replaceKBState({ ...urlState, query });
  };

  const handleCloseMode = () => {
    state.setMode("detail");
    pushKBState({ ...urlState, mode: "detail" });
  };

  const handleCreateCancel = () => {
    state.handleCreateCancel();
    pushKBState({ ...urlState, mode: "detail", entryId: null });
  };

  const handleCreated = (entryId: string) => {
    state.handleCreated(entryId);
    pushKBState({ ...urlState, mode: "detail", entryId });
  };

  const handleDeleted = () => {
    state.handleDeleted();
    pushKBState({ ...urlState, mode: "detail", entryId: null });
  };

  const handleAssistedCancel = () => {
    state.handleAssistedCancel();
    pushKBState({ ...urlState, mode: "detail", entryId: null });
  };

  return {
    buildKBHref,
    handleAnalyze,
    handleAssistedCancel,
    handleCloseMode,
    handleConsistencyCheck,
    handleCreateAssisted,
    handleCreateCancel,
    handleCreateNew,
    handleCreated,
    handleDeleted,
    handleSearchQueryChange,
    handleSelectEntry,
    handleShowGraph,
    handleShowWiki,
    handleTypeChange,
  };
}
