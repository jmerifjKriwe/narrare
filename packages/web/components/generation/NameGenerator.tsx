"use client";

import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { generationApi } from "@/lib/api/client";
import type { Gender, NameGenerateRequest, NameGenerateResponse, NameType } from "@/types";
import { NameResults } from "./NameResults";

const NAME_TYPES: { value: NameType; labelKey: string }[] = [
  { value: "character", labelKey: "character" },
  { value: "place", labelKey: "place" },
  { value: "organization", labelKey: "organization" },
  { value: "item", labelKey: "item" },
];

const CULTURES = [
  { value: "fantasy", labelKey: "fantasy" },
  { value: "modern", labelKey: "modern" },
  { value: "scifi", labelKey: "scifi" },
];

const GENDERS: { value: Gender; labelKey: string }[] = [
  { value: "any", labelKey: "anyGender" },
  { value: "male", labelKey: "male" },
  { value: "female", labelKey: "female" },
  { value: "neutral", labelKey: "neutral" },
];

const LANGUAGES = [
  { value: "en", labelKey: "langEnglish" },
  { value: "de", labelKey: "langGerman" },
  { value: "fr", labelKey: "langFrench" },
];

interface NameGeneratorProps {
  readonly projectId: string;
}

export function NameGenerator({ projectId }: NameGeneratorProps) {
  const t = useTranslations("generation");

  const [nameType, setNameType] = useState<NameType>("character");
  const [culture, setCulture] = useState("fantasy");
  const [count, setCount] = useState(10);
  const [gender, setGender] = useState<Gender>("any");
  const [language, setLanguage] = useState("en");
  const [results, setResults] = useState<NameGenerateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const generateMutation = useMutation({
    mutationFn: (request: NameGenerateRequest) => generationApi.generateNames(request),
    onSuccess: (data) => {
      setResults(data);
      setError(null);
    },
    onError: (e: unknown) => {
      setError(e instanceof Error ? e.message : "Generation failed");
      setResults(null);
    },
  });

  const handleGenerate = () => {
    if (count < 1 || count > 50) return;

    generateMutation.mutate({
      project_id: projectId,
      name_type: nameType,
      culture,
      count,
      gender,
      language,
    });
  };

  const nameTypeOptions = NAME_TYPES.map((nt) => ({
    value: nt.value,
    label: t(nt.labelKey),
  }));

  const cultureOptions = CULTURES.map((c) => ({
    value: c.value,
    label: t(c.labelKey),
  }));

  const genderOptions = GENDERS.map((g) => ({
    value: g.value,
    label: t(g.labelKey),
  }));

  const languageOptions = LANGUAGES.map((l) => ({
    value: l.value,
    label: t(l.labelKey),
  }));

  return (
    <div className="flex flex-col gap-6">
      <h2 className="text-xl font-semibold text-foreground">
        {t("nameGenerator")}
      </h2>

      {/* Form */}
      <div className="grid grid-cols-2 gap-4">
        <Select
          label={t("nameType")}
          value={nameType}
          onChange={(e) => setNameType(e.target.value as NameType)}
          options={nameTypeOptions}
        />

        <Select
          label={t("culture")}
          value={culture}
          onChange={(e) => setCulture(e.target.value)}
          options={cultureOptions}
        />

        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="name-count"
            className="text-[0.8125rem] font-semibold uppercase tracking-wider text-muted-foreground"
          >
            {t("count")}
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

        <Select
          label={t("gender")}
          value={gender}
          onChange={(e) => setGender(e.target.value as Gender)}
          options={genderOptions}
        />

        <Select
          label={t("language")}
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          options={languageOptions}
        />
      </div>

      {error && (
        <div
          className="bg-destructive/10 text-destructive rounded-lg p-3 text-[0.875rem]"
          role="alert"
        >
          {error}
        </div>
      )}

      <Button onClick={handleGenerate} loading={generateMutation.isPending} size="lg">
        {generateMutation.isPending ? t("generating") : t("generateNames")}
      </Button>

      {/* Results */}
      <NameResults results={results} isLoading={generateMutation.isPending} />
    </div>
  );
}
