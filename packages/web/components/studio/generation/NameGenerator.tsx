"use client";

/**
 * NameGenerator — AI name generation with cancel support.
 *
 * Generates names based on user parameters using the generation API.
 * §16 compliance: AbortController cancel, studio.aiActions.* labels.
 */

import { useMutation, useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import { generationApi, novelsApi } from "@/lib/api/client";
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

  const abortRef = useRef<AbortController | null>(null);

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

  const generateMutation = useMutation({
    mutationFn: (request: NameGenerateRequest) => {
      abortRef.current?.abort();
      abortRef.current = new AbortController();
      return generationApi.generateNames(request, abortRef.current.signal);
    },
    onSuccess: (data) => {
      setResults(data);
      setError(null);
    },
    onError: (e: unknown) => {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setError(e instanceof Error ? e.message : t("generation.generationFailed"));
      setResults(null);
    },
  });

  const handleGenerate = () => {
    if (count < 1 || count > 50) return;
    generateMutation.mutate({
      project_id: novelId,
      name_type: nameType,
      name_style: nameStyle,
      count,
      gender,
      explanation_language: explanationLanguage,
    });
  };

  const handleCancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

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
          disabled={generateMutation.isPending}
          className="flex-1 flex items-center justify-center gap-2 px-5 py-3 bg-primary text-primary-foreground rounded-lg text-[0.9375rem] font-medium hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {generateMutation.isPending ? tAction("generating") : t("generation.generateNames")}
        </button>
        {generateMutation.isPending && (
          <button
            type="button"
            onClick={handleCancel}
            className="flex items-center justify-center gap-1.5 px-4 py-3 text-sm text-muted-foreground hover:text-foreground border border-border rounded-lg hover:bg-muted transition-colors"
          >
            {tAction("stop")}
          </button>
        )}
      </div>

      <NameResults results={results} isLoading={generateMutation.isPending} />
    </div>
  );
}
