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
import type { StoryStructure, StoryTone } from "@/types"

const schema = z.object({
  title: z.string().min(1, "Title is required"),
  author: z.string(),
  genre: z.string(),
  logline: z.string(),
  story_structure: z.string(),
  tone: z.string(),
})
type FormData = z.infer<typeof schema>

export function WizardStep2({
  onNext,
  onBack,
}: {
  onNext: () => void
  onBack: () => void
}) {
  const t = useTranslations("wizard.step2")
  const tCommon = useTranslations("common")
  const tStructure = useTranslations("wizard.storyStructure")
  const tTone = useTranslations("wizard.tone")
  const { updateStep2, state } = useWizardStore()

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
      logline: state.logline,
      story_structure: state.story_structure,
      tone: state.tone,
    },
  })

  const onSubmit = async (data: FormData) => {
    await setupApi.validateStep2(data)
    updateStep2({
      title: data.title,
      author: data.author,
      genre: data.genre,
      logline: data.logline,
      story_structure: data.story_structure as StoryStructure,
      tone: data.tone as StoryTone,
    })
    onNext()
  }

  const structureOptions = [
    "three_act", "five_act", "heros_journey", "save_the_cat", "seven_point",
  ].map((v) => ({ value: v, label: tStructure(v as StoryStructure) }))

  const toneOptions = [
    "dramatic", "humorous", "suspenseful", "contemplative", "romantic", "dark", "adventurous",
  ].map((v) => ({ value: v, label: tTone(v as StoryTone) }))

  return (
    <div className="step">
      <div className="step-header">
        <h2 className="step-title">{t("title")}</h2>
        <p className="step-description">{t("description")}</p>
      </div>

      <form
        onSubmit={handleSubmit(onSubmit)}
        className="step-form"
      >
        <Input
          {...register("title")}
          label={t("novelTitle")}
          placeholder={t("novelTitlePlaceholder")}
          error={errors.title?.message}
          autoFocus
        />
        <Input
          {...register("author")}
          label={t("author")}
          placeholder={t("authorPlaceholder")}
        />
        <Input
          {...register("genre")}
          label={t("genre")}
          placeholder={t("genrePlaceholder")}
        />
        <Input
          {...register("logline")}
          label={t("logline")}
          placeholder={t("loglinePlaceholder")}
        />
        <Select
          {...register("story_structure")}
          label={t("structure")}
          options={structureOptions}
        />
        <Select
          {...register("tone")}
          label={t("tone")}
          options={toneOptions}
        />

        <div className="step-actions">
          <Button type="button" variant="secondary" onClick={onBack}>
            ← {tCommon("back")}
          </Button>
          <Button type="submit" loading={isSubmitting}>
            {tCommon("next")} →
          </Button>
        </div>
      </form>
    </div>
  )
}
