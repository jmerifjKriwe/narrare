"use client";

import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { generationApi } from "@/lib/api/client";
import { NAME_STYLE_SUGGESTIONS } from "@/lib/constants/name-styles";
import type { Gender, NameGenerateRequest, NameGenerateResponse, NameType } from "@/types";
import { NameResults } from "./NameResults";

const NAME_STYLE_DATALIST_ID = "name-style-suggestions";

const NAME_TYPES: { value: NameType; labelKey: string }[] = [
  { value: "character", labelKey: "character" },
  { value: "place", labelKey: "place" },
  { value: "organization", labelKey: "organization" },
  { value: "item", labelKey: "item" },
];

const GENDERS: { value: Gender; labelKey: string }[] = [
  { value: "any", labelKey: "anyGender" },
  { value: "male", labelKey: "male" },
  { value: "female", labelKey: "female" },
  { value: "neutral", labelKey: "neutral" },
];

const EXPLANATION_LANGUAGES = [
  { value: "en", labelKey: "langEnglish" },
  { value: "de", labelKey: "langGerman" },
  { value: "fr", labelKey: "langFrench" },
];

interface NameGeneratorProps {
  readonly novelId: string;
}

export function NameGenerator({ novelId }: NameGeneratorProps) {
  const t = useTranslations("studio");

  const [nameType, setNameType] = useState<NameType>("character");
  const [nameStyle, setNameStyle] = useState("Fantasy");
  const [count, setCount] = useState(10);
  const [gender, setGender] = useState<Gender>("any");
  const [explanationLanguage, setExplanationLanguage] = useState("en");
  const [results, setResults] = useState<NameGenerateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const generateMutation = useMutation({
    mutationFn: (request: NameGenerateRequest) => generationApi.generateNames(request),
    onSuccess: (data) => {
      setResults(data);
      setError(null);
    },
    onError: (e: unknown) => {
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

  const nameTypeOptions = NAME_TYPES.map((nt) => ({
    value: nt.value,
    label: t(`generation.${nt.labelKey}`),
  }));

  const genderOptions = GENDERS.map((g) => ({
    value: g.value,
    label: t(`generation.${g.labelKey}`),
  }));

  const languageOptions = EXPLANATION_LANGUAGES.map((l) => ({
    value: l.value,
    label: t(`generation.${l.labelKey}`),
  }));

  return (
    <div className="flex flex-col gap-6">
      <h2 className="text-xl font-semibold text-foreground">{t("generation.nameGenerator")}</h2>

      {/* Form */}
      <div className="grid grid-cols-2 gap-4">
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="name-type"
            className="text-[0.8125rem] font-semibold uppercase tracking-wider text-muted-foreground"
          >
            {t("generation.nameType")}
          </label>
          <select
            id="name-type"
            value={nameType}
            onChange={(e) => setNameType(e.target.value as NameType)}
            className="w-full px-4 py-3 border border-border rounded-lg bg-card text-foreground text-[0.9375rem] transition-all duration-200 outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
          >
            {nameTypeOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="name-style"
            className="text-[0.8125rem] font-semibold uppercase tracking-wider text-muted-foreground"
          >
            {t("generation.nameStyle")}
          </label>
          <input
            id="name-style"
            type="text"
            list={NAME_STYLE_DATALIST_ID}
            value={nameStyle}
            onChange={(e) => setNameStyle(e.target.value)}
            className="w-full px-4 py-3 border border-border rounded-lg bg-card text-foreground text-[0.9375rem] transition-all duration-200 outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
          />
          <datalist id={NAME_STYLE_DATALIST_ID}>
            {NAME_STYLE_SUGGESTIONS.map((suggestion) => (
              <option key={suggestion} value={suggestion} />
            ))}
          </datalist>
        </div>

        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="name-count"
            className="text-[0.8125rem] font-semibold uppercase tracking-wider text-muted-foreground"
          >
            {t("generation.count")}
          </label>
          <input
            id="name-count"
            type="number"
            min={1}
            max={50}
            value={count}
            onChange={(e) => setCount(Math.max(1, Math.min(50, Number(e.target.value))))}
            className="w-full px-4 py-3 border border-border rounded-lg bg-card text-foreground text-[0.9375rem] transition-all duration-200 outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="name-gender"
            className="text-[0.8125rem] font-semibold uppercase tracking-wider text-muted-foreground"
          >
            {t("generation.gender")}
          </label>
          <select
            id="name-gender"
            value={gender}
            onChange={(e) => setGender(e.target.value as Gender)}
            className="w-full px-4 py-3 border border-border rounded-lg bg-card text-foreground text-[0.9375rem] transition-all duration-200 outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
          >
            {genderOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="name-explanation-language"
            className="text-[0.8125rem] font-semibold uppercase tracking-wider text-muted-foreground"
          >
            {t("generation.explanationLanguage")}
          </label>
          <select
            id="name-explanation-language"
            value={explanationLanguage}
            onChange={(e) => setExplanationLanguage(e.target.value)}
            className="w-full px-4 py-3 border border-border rounded-lg bg-card text-foreground text-[0.9375rem] transition-all duration-200 outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
          >
            {languageOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div
          className="bg-destructive/10 text-destructive rounded-lg p-3 text-[0.875rem]"
          role="alert"
        >
          {error}
        </div>
      )}

      <button
        type="button"
        onClick={handleGenerate}
        disabled={generateMutation.isPending}
        className="flex items-center justify-center gap-2 px-5 py-3 bg-primary text-primary-foreground rounded-lg text-[0.9375rem] font-medium hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {generateMutation.isPending ? t("generation.generating") : t("generation.generateNames")}
      </button>

      {/* Results */}
      <NameResults results={results} isLoading={generateMutation.isPending} />
    </div>
  );
}
