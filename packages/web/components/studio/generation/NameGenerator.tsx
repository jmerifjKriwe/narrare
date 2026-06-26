"use client";

/**
 * NameGenerator — AI name generation with §16 AI-Interaction Standards.
 *
 * Uses useAIOperation for lifecycle management with structured error
 * mapping and cancel support. Keeps TanStack Query for novel data fetching.
 *
 * @module NameGenerator
 */

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import { mapRestApiError } from "@/lib/api/ai-rest-error";
import { generationApi, novelsApi } from "@/lib/api/client";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import type { Gender, NameGenerateRequest, NameGenerateResponse, NameType } from "@/types";
import { NameGeneratorForm } from "./NameGeneratorForm";
import { NameResults } from "./NameResults";

interface NameGeneratorProps {
  readonly novelId: string;
}

export function NameGenerator({ novelId }: NameGeneratorProps) {
  const t = useTranslations("studio");
  const tAction = useTranslations("studio.aiActions");

  const [nameType, setNameType] = useState<NameType>("character");
  const [nameStyle, setNameStyle] = useState("Fantasy");
  const [count, setCount] = useState(10);
  const [gender, setGender] = useState<Gender>("any");
  const [explanationLanguage, setExplanationLanguage] = useState("en");
  const [results, setResults] = useState<NameGenerateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const requestRef = useRef<NameGenerateRequest | null>(null);

  // Fetch novel to determine default explanation_language from writing_language
  const { data: novel } = useQuery({
    queryKey: ["novels", novelId],
    queryFn: () => novelsApi.get(novelId),
  });

  const languageSynced = useRef(false);
  useEffect(() => {
    if (novel?.writing_language && !languageSynced.current) {
      setExplanationLanguage(novel.writing_language);
      languageSynced.current = true;
    }
  }, [novel?.writing_language]);

  // -- AI operation lifecycle via useAIOperation --

  const aiOp = useAIOperation<NameGenerateResponse>({
    execute: async (signal) => {
      const request = requestRef.current;
      if (!request) throw new Error("No request parameters");
      return generationApi.generateNames(request, signal);
    },
    errorMapper: mapRestApiError,
    onSuccess: (data) => {
      setResults(data);
      setError(null);
    },
    onError: (errResponse) => {
      setError(errResponse.userMessage);
      setResults(null);
    },
    connectionLossTimeout: 15_000,
  });

  const handleGenerate = () => {
    if (count < 1 || count > 50) return;
    requestRef.current = {
      project_id: novelId,
      name_type: nameType,
      name_style: nameStyle,
      count,
      gender,
      explanation_language: explanationLanguage,
    };
    aiOp.start();
  };

  const handleCancel = useCallback(() => {
    aiOp.cancel();
  }, [aiOp]);

  // Cleanup on unmount. aiOp.cancel is a stable ref (created once by the hook's
  // lifecycleRef), so this effect runs a single time — cancelling only when the
  // component unmounts, not on every state transition (which would abort the
  // operation the moment it enters "loading"). See CharacterArcPanel for the
  // same pattern.
  const cancelOp = aiOp.cancel;
  useEffect(() => {
    return () => cancelOp();
  }, [cancelOp]);

  const isPending = aiOp.isLoading || aiOp.isStreaming;

  return (
    <div className="flex flex-col gap-6">
      <h2 className="text-xl font-semibold text-foreground">{t("generation.nameGenerator")}</h2>

      <NameGeneratorForm
        nameType={nameType}
        nameStyle={nameStyle}
        count={count}
        gender={gender}
        explanationLanguage={explanationLanguage}
        onNameTypeChange={setNameType}
        onNameStyleChange={setNameStyle}
        onCountChange={setCount}
        onGenderChange={setGender}
        onLanguageChange={setExplanationLanguage}
      />

      {error && (
        <div
          className="bg-destructive/10 text-destructive rounded-lg p-3 text-[0.875rem]"
          role="alert"
        >
          {error}
        </div>
      )}

      <div className="flex gap-2">
        <button
          type="button"
          onClick={handleGenerate}
          disabled={isPending}
          className="flex-1 flex items-center justify-center gap-2 px-5 py-3 bg-primary text-primary-foreground rounded-lg text-[0.9375rem] font-medium hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isPending ? tAction("generating") : t("generation.generateNames")}
        </button>
        {isPending && (
          <button
            type="button"
            onClick={handleCancel}
            className="flex items-center justify-center gap-1.5 px-4 py-3 text-sm text-muted-foreground hover:text-foreground border border-border rounded-lg hover:bg-muted transition-colors"
          >
            {tAction("stop")}
          </button>
        )}
      </div>

      <NameResults results={results} isLoading={isPending} novelId={novelId} nameType={nameType} />
    </div>
  );
}
