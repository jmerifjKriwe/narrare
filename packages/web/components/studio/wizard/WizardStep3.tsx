"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useLocale, useTranslations } from "next-intl";
import { useMemo } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { setupApi } from "@/lib/api/client";
import { BUNDLED_TONES } from "@/lib/constants/tones";
import { useWizardStore } from "@/lib/stores/wizardStore";
import type { StoryStructure, StoryTone } from "@/types";
import { NovelMetadataFields } from "./NovelMetadataFields";

// Validation messages are localized, so the schema is built inside the
// component (see useMemo below) and only the form shape is typed here.
type FormData = {
  title: string;
  author: string;
  genre: string;
  writing_language: string;
  logline: string;
  story_structure: string;
  tone: string;
};

interface WizardStep3Props {
  onNext: () => void;
  onBack: () => void;
}

export function WizardStep3({ onNext, onBack }: WizardStep3Props) {
  const t = useTranslations("studio");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const { updateStep2, state } = useWizardStore();

  // Build the Zod schema inside the component so validation messages can be
  // localized. Memoized on `t` so it rebuilds when the locale changes.
  const schema = useMemo(
    () =>
      z.object({
        title: z.string().min(1, t("wizard.validation.titleRequired")),
        author: z.string(),
        genre: z.string(),
        writing_language: z.string().max(100, t("wizard.validation.languageTooLong")),
        logline: z.string(),
        story_structure: z.string(),
        tone: z.string(),
      }),
    [t],
  );

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      title: state.title,
      author: state.author,
      genre: state.genre,
      writing_language: state.writing_language || locale,
      logline: state.logline,
      story_structure: state.story_structure,
      tone: state.tone,
    },
    values: {
      title: state.title,
      author: state.author,
      genre: state.genre,
      writing_language: state.writing_language || locale,
      logline: state.logline,
      story_structure: state.story_structure,
      tone: state.tone,
    },
  });

  const onSubmit = async (data: FormData) => {
    await setupApi.validateStep2(data);
    updateStep2({
      title: data.title,
      author: data.author,
      genre: data.genre,
      writing_language: data.writing_language,
      logline: data.logline,
      story_structure: data.story_structure as StoryStructure,
      tone: data.tone as StoryTone,
    });
    onNext();
  };

  const structureOptions = [
    "three_act",
    "five_act",
    "heros_journey",
    "save_the_cat",
    "seven_point",
  ].map((v) => ({ value: v, label: t(`wizard.storyStructure.${v}` as const) }));
  const toneOptions = BUNDLED_TONES.map((opt) => ({ value: opt.value, label: t(opt.label) }));

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-xl font-semibold mb-1">{t("wizard.step3.title")}</h2>
        <p className="text-muted-foreground text-[0.9375rem]">{t("wizard.step3.description")}</p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-5">
        <NovelMetadataFields
          register={register}
          structureOptions={structureOptions}
          toneOptions={toneOptions}
          translations={{
            novelTitle: t("wizard.step3.novelTitle"),
            novelTitlePlaceholder: t("wizard.step3.novelTitlePlaceholder"),
            author: t("wizard.step3.author"),
            authorPlaceholder: t("wizard.step3.authorPlaceholder"),
            genre: t("wizard.step3.genre"),
            genrePlaceholder: t("wizard.step3.genrePlaceholder"),
            writingLanguage: t("wizard.step3.writingLanguage"),
            writingLanguagePlaceholder: t("wizard.step3.writingLanguagePlaceholder"),
            logline: t("wizard.step3.logline"),
            loglinePlaceholder: t("wizard.step3.loglinePlaceholder"),
            structure: t("wizard.step3.structure"),
            tone: t("wizard.step3.tone"),
          }}
          titleError={errors.title?.message}
        />

        <div className="flex justify-end gap-3 mt-4">
          <button
            type="button"
            onClick={onBack}
            data-testid="wizard-back"
            className="px-6 py-2 bg-muted rounded-md hover:bg-accent transition-colors text-sm"
          >
            ← {tCommon("back")}
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            data-testid="wizard-next"
            className="px-6 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity text-sm disabled:opacity-50"
          >
            {isSubmitting ? `${tCommon("next")}…` : `${tCommon("next")} →`}
          </button>
        </div>
      </form>
    </div>
  );
}
