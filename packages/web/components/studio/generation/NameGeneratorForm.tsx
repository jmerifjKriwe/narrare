"use client";

/**
 * NameGeneratorForm — Form fields for the name generator.
 *
 * Extracted from NameGenerator to keep file under 200-line limit (RULE-04).
 * Contains type/style/count/gender/language inputs.
 */

import { useTranslations } from "next-intl";
import { NAME_STYLE_SUGGESTIONS } from "@/lib/constants/name-styles";
import type { Gender, NameType } from "@/types";

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

const LANGUAGES = [
  { value: "en", labelKey: "langEnglish" },
  { value: "de", labelKey: "langGerman" },
  { value: "fr", labelKey: "langFrench" },
];

interface NameGeneratorFormProps {
  readonly nameType: NameType;
  readonly nameStyle: string;
  readonly count: number;
  readonly gender: Gender;
  readonly explanationLanguage: string;
  readonly onNameTypeChange: (value: NameType) => void;
  readonly onNameStyleChange: (value: string) => void;
  readonly onCountChange: (value: number) => void;
  readonly onGenderChange: (value: Gender) => void;
  readonly onLanguageChange: (value: string) => void;
}

export function NameGeneratorForm({
  nameType,
  nameStyle,
  count,
  gender,
  explanationLanguage,
  onNameTypeChange,
  onNameStyleChange,
  onCountChange,
  onGenderChange,
  onLanguageChange,
}: NameGeneratorFormProps) {
  const t = useTranslations("studio");

  return (
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
          onChange={(e) => onNameTypeChange(e.target.value as NameType)}
          className="w-full px-4 py-3 border border-border rounded-lg bg-card text-foreground text-[0.9375rem] transition-all duration-200 outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
        >
          {NAME_TYPES.map((nt) => (
            <option key={nt.value} value={nt.value}>
              {t(`generation.${nt.labelKey}`)}
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
          onChange={(e) => onNameStyleChange(e.target.value)}
          className="w-full px-4 py-3 border border-border rounded-lg bg-card text-foreground text-[0.9375rem] transition-all duration-200 outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
        />
        <datalist id={NAME_STYLE_DATALIST_ID}>
          {NAME_STYLE_SUGGESTIONS.map((s) => (
            <option key={s} value={s} />
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
          onChange={(e) => onCountChange(Math.max(1, Math.min(50, Number(e.target.value))))}
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
          onChange={(e) => onGenderChange(e.target.value as Gender)}
          className="w-full px-4 py-3 border border-border rounded-lg bg-card text-foreground text-[0.9375rem] transition-all duration-200 outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
        >
          {GENDERS.map((g) => (
            <option key={g.value} value={g.value}>
              {t(`generation.${g.labelKey}`)}
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
          onChange={(e) => onLanguageChange(e.target.value)}
          className="w-full px-4 py-3 border border-border rounded-lg bg-card text-foreground text-[0.9375rem] transition-all duration-200 outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
        >
          {LANGUAGES.map((l) => (
            <option key={l.value} value={l.value}>
              {t(`generation.${l.labelKey}`)}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
