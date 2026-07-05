"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslations } from "next-intl";
import { useMemo } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { setupApi } from "@/lib/api/client";
import { useWizardStore } from "@/lib/stores/wizardStore";

// Validation messages are localized, so the schema is built inside the
// component (see useMemo below) and only the form shape is typed here.
type FormData = {
  project_name: string;
  writing_language: string;
  autosave_interval: number;
};

interface WizardStep1Props {
  onNext: () => void;
}

export function WizardStep1({ onNext }: WizardStep1Props) {
  const t = useTranslations("studio");
  const tCommon = useTranslations("common");
  const { updateStep1, state } = useWizardStore();

  // Build the Zod schema inside the component so validation messages can be
  // localized. Memoized on `t` so it rebuilds when the locale changes.
  const schema = useMemo(
    () =>
      z.object({
        project_name: z
          .string()
          .min(1, t("wizard.validation.projectNameRequired"))
          .regex(/^[^/\\:*?"<>|]*$/, t("wizard.validation.projectNameInvalidChars")),
        writing_language: z.string().max(100, t("wizard.validation.languageTooLong")),
        autosave_interval: z.number().min(0).max(3600),
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
      project_name: state.project_name,
      writing_language: state.writing_language || "en",
      autosave_interval: state.autosave_interval,
    },
  });

  const onSubmit = async (data: FormData) => {
    await setupApi.validateStep1(data);
    updateStep1(data);
    onNext();
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-xl font-semibold mb-1">{t("wizard.step1.title")}</h2>
        <p className="text-muted-foreground text-[0.9375rem]">{t("wizard.step1.description")}</p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-5">
        <div>
          <label htmlFor="project_name" className="block text-sm font-medium mb-1.5">
            {t("wizard.step1.projectName")}
          </label>
          <input
            id="project_name"
            type="text"
            {...register("project_name")}
            placeholder={t("wizard.step1.projectNamePlaceholder")}
            className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
          />
          {errors.project_name && (
            <p className="text-sm text-destructive mt-1">{errors.project_name.message}</p>
          )}
        </div>

        <div>
          <label htmlFor="writing_language" className="block text-sm font-medium mb-1.5">
            {t("wizard.step1.language")}
          </label>
          <select
            id="writing_language"
            {...register("writing_language")}
            className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
          >
            <option value="en">{t("wizard.step1.langEn")}</option>
            <option value="de">{t("wizard.step1.langDe")}</option>
            <option value="fr">{t("wizard.step1.langFr")}</option>
          </select>
        </div>

        <div>
          <label htmlFor="autosave_interval" className="block text-sm font-medium mb-1.5">
            {t("wizard.step1.autosave")}
          </label>
          <input
            id="autosave_interval"
            type="number"
            {...register("autosave_interval", { valueAsNumber: true })}
            min={0}
            max={3600}
            className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
          />
          <p className="text-xs text-muted-foreground mt-1">{t("wizard.step1.autosaveHint")}</p>
        </div>

        <div className="flex justify-end gap-3 mt-4">
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
