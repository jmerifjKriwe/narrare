"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useLocale, useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { setupApi } from "@/lib/api/client";
import { GENRE_SUGGESTIONS } from "@/lib/constants/genres";
import { BUNDLED_TONES } from "@/lib/constants/tones";
import { useWizardStore } from "@/lib/stores/wizardStore";
import type { StoryStructure, StoryTone } from "@/types";

const GENRE_DATALIST_ID = "genre-suggestions";

const schema = z.object({
  title: z.string().min(1, "Title is required"),
  author: z.string(),
  genre: z.string(),
  writing_language: z.string().max(100, "Language must be 100 characters or less"),
  logline: z.string(),
  story_structure: z.string(),
  tone: z.string(),
});
type FormData = z.infer<typeof schema>;

interface WizardStep3Props {
  onNext: () => void;
  onBack: () => void;
}

export function WizardStep3({ onNext, onBack }: WizardStep3Props) {
  const t = useTranslations("studio");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const { updateStep2, state } = useWizardStore();

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
    // Sync external store changes (e.g. demo metadata prefill from Step 2)
    // into the form without requiring manual reset() calls.
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

  const structureOptions: { value: string; label: string }[] = [
    "three_act",
    "five_act",
    "heros_journey",
    "save_the_cat",
    "seven_point",
  ].map((v) => ({ value: v, label: t(`wizard.storyStructure.${v}` as const) }));

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-xl font-semibold mb-1">{t("wizard.step3.title")}</h2>
        <p className="text-muted-foreground text-[0.9375rem]">{t("wizard.step3.description")}</p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-5">
        <div>
          <label htmlFor="novel_title" className="block text-sm font-medium mb-1.5">
            {t("wizard.step3.novelTitle")}
          </label>
          <input
            id="novel_title"
            type="text"
            {...register("title")}
            placeholder={t("wizard.step3.novelTitlePlaceholder")}
            className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
          />
          {errors.title && <p className="text-sm text-destructive mt-1">{errors.title.message}</p>}
        </div>

        <div>
          <label htmlFor="author" className="block text-sm font-medium mb-1.5">
            {t("wizard.step3.author")}
          </label>
          <input
            id="author"
            type="text"
            {...register("author")}
            placeholder={t("wizard.step3.authorPlaceholder")}
            className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
          />
        </div>

        <div>
          <label htmlFor="genre" className="block text-sm font-medium mb-1.5">
            {t("wizard.step3.genre")}
          </label>
          <input
            id="genre"
            type="text"
            list={GENRE_DATALIST_ID}
            {...register("genre")}
            placeholder={t("wizard.step3.genrePlaceholder")}
            className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
          />
          <datalist id={GENRE_DATALIST_ID}>
            {GENRE_SUGGESTIONS.map((suggestion) => (
              <option key={suggestion} value={suggestion} />
            ))}
          </datalist>
        </div>

        <div>
          <label htmlFor="writing_language" className="block text-sm font-medium mb-1.5">
            {t("wizard.step3.writingLanguage")}
          </label>
          <input
            id="writing_language"
            type="text"
            {...register("writing_language")}
            placeholder={t("wizard.step3.writingLanguagePlaceholder")}
            className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
          />
        </div>

        <div>
          <label htmlFor="logline" className="block text-sm font-medium mb-1.5">
            {t("wizard.step3.logline")}
          </label>
          <input
            id="logline"
            type="text"
            {...register("logline")}
            placeholder={t("wizard.step3.loglinePlaceholder")}
            className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
          />
        </div>

        <div>
          <label htmlFor="story_structure" className="block text-sm font-medium mb-1.5">
            {t("wizard.step3.structure")}
          </label>
          <select
            id="story_structure"
            {...register("story_structure")}
            className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
          >
            {structureOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="tone" className="block text-sm font-medium mb-1.5">
            {t("wizard.step3.tone")}
          </label>
          <select
            id="tone"
            {...register("tone")}
            className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
          >
            {BUNDLED_TONES.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {t(opt.label)}
              </option>
            ))}
          </select>
        </div>

        <div className="flex justify-end gap-3 mt-4">
          <button
            type="button"
            onClick={onBack}
            className="px-6 py-2 bg-muted rounded-md hover:bg-accent transition-colors text-sm"
          >
            ← {tCommon("back")}
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            className="px-6 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity text-sm disabled:opacity-50"
          >
            {isSubmitting ? `${tCommon("next")}…` : `${tCommon("next")} →`}
          </button>
        </div>
      </form>
    </div>
  );
}
