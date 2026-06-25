"use client";

/**
 * CharacterArcPanel — AI character development arc analysis.
 *
 * Lets the author describe a character (name + optional current/goal state)
 * and generates a structured arc (type, phases, relationships, conflict,
 * resolution). Uses useAIOperation (ADR-043) for the lifecycle with the
 * REST error mapper and connection-loss detection disabled (this is a
 * single-shot REST call, not an SSE stream).
 *
 * @module CharacterArcPanel
 */

import { Loader2, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { mapRestApiError } from "@/lib/api/ai-rest-error";
import { type CharacterArcResponse, generateCharacterArc } from "@/lib/api/character-arc";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import { CharacterArcResult } from "./CharacterArcResult";

interface CharacterArcPanelProps {
  readonly novelId: string;
}

export function CharacterArcPanel({ novelId }: CharacterArcPanelProps) {
  const t = useTranslations("studio");
  const tAction = useTranslations("studio.aiActions");

  const [characterName, setCharacterName] = useState("");
  const [currentState, setCurrentState] = useState("");
  const [goalState, setGoalState] = useState("");
  const [result, setResult] = useState<CharacterArcResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const requestRef = useRef<{
    character_name: string;
    character_current_state: string;
    character_goal_state: string;
  } | null>(null);

  // -- AI operation lifecycle (ADR-043) --
  // connectionLossTimeout: 0 — this is a single-shot REST call, not an SSE
  // stream, so connection-loss detection is disabled to avoid false positives
  // on slow LLM responses.
  const aiOp = useAIOperation<CharacterArcResponse>({
    execute: async (signal) => {
      const request = requestRef.current;
      if (!request) throw new Error("No request parameters");
      return generateCharacterArc(novelId, request, signal);
    },
    errorMapper: mapRestApiError,
    connectionLossTimeout: 0,
    onSuccess: (data) => {
      setResult(data);
      setError(null);
    },
    onError: (errResponse) => {
      setError(errResponse.userMessage);
      setResult(null);
    },
  });

  const isPending = aiOp.isLoading || aiOp.isStreaming;
  const canGenerate = characterName.trim().length > 0 && !isPending;

  // Cleanup on unmount. aiOp.cancel is a stable ref (created once by the hook's
  // lifecycleRef), so this effect runs a single time — cancelling only when the
  // component unmounts, not on every state transition (which would abort the
  // operation the moment it enters "loading").
  const cancelOp = aiOp.cancel;
  useEffect(() => {
    return () => cancelOp();
  }, [cancelOp]);

  const handleGenerate = () => {
    if (!canGenerate) return;
    requestRef.current = {
      character_name: characterName.trim(),
      character_current_state: currentState.trim(),
      character_goal_state: goalState.trim(),
    };
    setError(null);
    aiOp.start();
  };

  return (
    <div className="flex flex-col gap-4 p-4">
      <h2 className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
        <Sparkles className="h-4 w-4 text-[var(--color-accent)]" aria-hidden="true" />
        {t("characterArc.title")}
      </h2>

      {/* Form */}
      <form
        className="flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          handleGenerate();
        }}
      >
        <div className="flex flex-col gap-1">
          <label htmlFor="character-arc-name" className="text-xs font-medium text-muted-foreground">
            {t("characterArc.characterName")}
          </label>
          <input
            id="character-arc-name"
            type="text"
            value={characterName}
            onChange={(e) => setCharacterName(e.target.value)}
            maxLength={200}
            required
            className="rounded-md border border-border bg-background px-2.5 py-1.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label
            htmlFor="character-arc-current"
            className="text-xs font-medium text-muted-foreground"
          >
            {t("characterArc.currentState")}
          </label>
          <textarea
            id="character-arc-current"
            value={currentState}
            onChange={(e) => setCurrentState(e.target.value)}
            rows={2}
            className="resize-y rounded-md border border-border bg-background px-2.5 py-1.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="character-arc-goal" className="text-xs font-medium text-muted-foreground">
            {t("characterArc.goalState")}
          </label>
          <textarea
            id="character-arc-goal"
            value={goalState}
            onChange={(e) => setGoalState(e.target.value)}
            rows={2}
            className="resize-y rounded-md border border-border bg-background px-2.5 py-1.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
          />
        </div>

        <button
          type="button"
          onClick={handleGenerate}
          disabled={!canGenerate}
          className="flex items-center justify-center gap-1.5 rounded-md bg-[var(--color-accent)] px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isPending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              {t("characterArc.loading")}
            </>
          ) : (
            t("characterArc.generate")
          )}
        </button>

        {isPending && (
          <button
            type="button"
            onClick={() => aiOp.cancel()}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            {tAction("stop")}
          </button>
        )}
      </form>

      {/* Error */}
      {error && (
        <div
          className="rounded-lg bg-red-50 p-3 text-sm text-[var(--color-error)] dark:bg-red-950/40"
          role="alert"
        >
          {t("characterArc.error")}: {error}
        </div>
      )}

      {/* Result */}
      {result && <CharacterArcResult result={result} />}
    </div>
  );
}
