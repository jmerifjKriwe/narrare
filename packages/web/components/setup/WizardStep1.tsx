"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { setupApi } from "@/lib/api/client";
import { useWizardStore } from "@/lib/stores/wizardStore";

const schema = z.object({
  project_name: z
    .string()
    .min(1, "Project name is required")
    .regex(/^[^/\\:*?"<>|]*$/, "Project name contains invalid characters"),
  language: z.enum(["en", "de", "fr"]),
  autosave_interval: z.number().min(0).max(3600),
});
type FormData = z.infer<typeof schema>;

export function WizardStep1({ onNext }: { onNext: () => void }) {
  const t = useTranslations("wizard.step1");
  const { updateStep1, state } = useWizardStore();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      project_name: state.project_name,
      language: (state.language as "en" | "de" | "fr") || "en",
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
      <div className="flex items-center gap-3">
        <div>
          <h2 className="text-xl font-semibold mb-1" style={{ fontFamily: "var(--font-display)" }}>
            {t("title")}
          </h2>
          <p className="text-muted-foreground text-[0.9375rem]">{t("description")}</p>
        </div>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-5">
        <Input
          {...register("project_name")}
          label={t("projectName")}
          placeholder={t("projectNamePlaceholder")}
          error={errors.project_name?.message}
          autoFocus
        />

        <Select
          {...register("language")}
          label={t("language")}
          options={[
            { value: "en", label: "English" },
            { value: "de", label: "Deutsch" },
            { value: "fr", label: "Français" },
          ]}
        />

        <Input
          {...register("autosave_interval", { valueAsNumber: true })}
          type="number"
          label={t("autosave")}
          min={0}
          max={3600}
          hint="0 = off, max 3600 seconds"
        />

        <div className="flex justify-end gap-3 mt-4">
          <Button type="submit" loading={isSubmitting}>
            {useTranslations("common")("next")} →
          </Button>
        </div>
      </form>
    </div>
  );
}
