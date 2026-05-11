"use client"

import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useTranslations } from "next-intl"
import { useWizardStore } from "@/lib/stores/wizardStore"
import { setupApi } from "@/lib/api/client"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Select } from "@/components/ui/Select"

const schema = z.object({
  project_name: z
    .string()
    .min(1, "Project name is required")
    .regex(/^[^/\\:*?"<>|]*$/, "Project name contains invalid characters"),
  language: z.enum(["en", "de", "fr"]),
  autosave_interval: z.coerce.number().min(0).max(3600),
})
type FormData = z.infer<typeof schema>

export function WizardStep1({ onNext }: { onNext: () => void }) {
  const t = useTranslations("wizard.step1")
  const { updateStep1, state } = useWizardStore()

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
  })

  const onSubmit = async (data: FormData) => {
    await setupApi.validateStep1(data)
    updateStep1(data)
    onNext()
  }

  return (
    <div className="step">
      <div className="step-header">
        <h2 className="step-title">{t("title")}</h2>
        <p className="step-description">{t("description")}</p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="step-form">
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
          {...register("autosave_interval")}
          type="number"
          label={t("autosave")}
          min={0}
          max={3600}
          hint="0 = off, max 3600 seconds"
        />

        <div className="step-actions">
          <Button type="submit" loading={isSubmitting}>
            {useTranslations("common")("next")} →
          </Button>
        </div>
      </form>

      <StepStyles />
    </div>
  )
}

function StepStyles() {
  return (
    <style jsx global>{`
      .step { display: flex; flex-direction: column; gap: var(--space-6); }
      .step-header { }
      .step-title { font-size: 1.25rem; font-weight: 600; margin-bottom: var(--space-1); }
      .step-description { color: var(--color-text-secondary); font-size: 0.9375rem; }
      .step-form { display: flex; flex-direction: column; gap: var(--space-4); }
      .step-actions { display: flex; justify-content: flex-end; gap: var(--space-3); margin-top: var(--space-2); }
    `}</style>
  )
}
