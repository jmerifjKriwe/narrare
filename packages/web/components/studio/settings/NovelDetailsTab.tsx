"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { SeriesVoiceOptOutCard } from "@/components/series/SeriesVoiceOptOutCard";
import { novelsApi, tonesApi } from "@/lib/api/client";
import type { Novel } from "@/types";
import { StructureChangeDialog } from "../planning/StructureChangeDialog";
import { BasicInfoCard } from "./_components/BasicInfoCard";
import type { NovelFormState } from "./_components/buildChangedPayload";
import { buildChangedPayload } from "./_components/buildChangedPayload";
import { NovelDetailsHeader } from "./_components/NovelDetailsHeader";
import { SaveFooter } from "./_components/SaveFooter";
import { StoryCard } from "./_components/StoryCard";
import { SummaryCard } from "./_components/SummaryCard";
import { useStructureChangeGuard } from "./_components/useStructureChangeGuard";

// --- Types ---

interface NovelDetailsTabProps {
  novelId: string;
}

// --- Component ---

export function NovelDetailsTab({ novelId }: NovelDetailsTabProps) {
  const t = useTranslations("studio");
  const queryClient = useQueryClient();

  // Fetch novel data
  const { data: novel, isLoading } = useQuery({
    queryKey: ["novels", novelId],
    queryFn: () => novelsApi.get(novelId),
  });

  // Local state for each editable field
  const [localTitle, setLocalTitle] = useState("");
  const [localAuthor, setLocalAuthor] = useState("");
  const [localWritingLanguage, setLocalWritingLanguage] = useState("en");
  const [localGenre, setLocalGenre] = useState("");
  const [localTone, setLocalTone] = useState("");
  const [localStoryStructure, setLocalStoryStructure] = useState("three_act");
  const [localLogline, setLocalLogline] = useState("");
  const [localSynopsis, setLocalSynopsis] = useState("");
  const [dirty, setDirty] = useState(false);

  // Custom tones from API
  const { data: customTones } = useQuery({
    queryKey: ["customTones"],
    queryFn: () => tonesApi.list(),
  });

  // Structure change dialog guard (extracted — RULE-04).
  const structureGuard = useStructureChangeGuard({ novel });

  // Sync novel data → local state when query resolves
  useEffect(() => {
    if (novel) {
      setLocalTitle(novel.title);
      setLocalAuthor(novel.author);
      setLocalWritingLanguage(novel.writing_language);
      setLocalGenre(novel.genre);
      setLocalTone(novel.tone);
      setLocalStoryStructure(novel.story_structure);
      setLocalLogline(novel.logline);
      setLocalSynopsis(novel.synopsis);
    }
  }, [novel]);

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: (payload: Partial<Novel>) => novelsApi.update(novelId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["novels"] });
      setDirty(false);
    },
  });

  function handleSave() {
    if (!novel) return;
    const form: NovelFormState = {
      title: localTitle,
      author: localAuthor,
      writingLanguage: localWritingLanguage,
      genre: localGenre,
      tone: localTone,
      storyStructure: localStoryStructure,
      logline: localLogline,
      synopsis: localSynopsis,
    };
    const payload = buildChangedPayload(form, novel);

    // Story-structure change → open the remap dialog instead of direct save
    // (the guard returns the structure-stripped payload to apply immediately).
    const { intercepted, immediatePayload } = structureGuard.intercept(payload);
    if (intercepted) {
      if (Object.keys(immediatePayload).length > 0) {
        saveMutation.mutate(immediatePayload);
      }
      return;
    }

    if (Object.keys(payload).length > 0) {
      saveMutation.mutate(payload);
    }
  }

  // Field change handlers — all set dirty
  const handleChange = (setter: (v: string) => void) => (value: string) => {
    setter(value);
    setDirty(true);
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div>
      <NovelDetailsHeader
        title={t("settings.novelDetailsSection.title")}
        description={t("settings.novelDetailsSection.description")}
      />

      <div className="space-y-4">
        <BasicInfoCard
          localTitle={localTitle}
          localAuthor={localAuthor}
          localWritingLanguage={localWritingLanguage}
          onTitleChange={handleChange(setLocalTitle)}
          onAuthorChange={handleChange(setLocalAuthor)}
          onWritingLanguageChange={handleChange(setLocalWritingLanguage)}
          t={t}
        />

        <StoryCard
          localGenre={localGenre}
          localTone={localTone}
          localStoryStructure={localStoryStructure}
          onGenreChange={handleChange(setLocalGenre)}
          onToneChange={handleChange(setLocalTone)}
          onStoryStructureChange={handleChange(setLocalStoryStructure)}
          customTones={customTones}
          t={t}
        />

        <SummaryCard
          localLogline={localLogline}
          localSynopsis={localSynopsis}
          onLoglineChange={handleChange(setLocalLogline)}
          onSynopsisChange={handleChange(setLocalSynopsis)}
          t={t}
        />

        {/* Spec 3: per-novel series-voice opt-out. Self-hides for standalone novels. */}
        <SeriesVoiceOptOutCard novelId={novelId} seriesId={novel?.series_id ?? null} />

        <SaveFooter
          dirty={dirty}
          isSaving={saveMutation.isPending}
          isError={saveMutation.isError}
          onSave={handleSave}
          errorText={t("settings.novelDetailsSection.saveError")}
          saveText={t("settings.ai.save")}
          loadingText={t("settings.ai.loading")}
        />
      </div>

      {/* Structure Change Dialog */}
      {structureGuard.pendingStructure && (
        <StructureChangeDialog
          open={structureGuard.remapDialogOpen}
          novelId={novelId}
          newStructure={structureGuard.pendingStructure}
          currentStructure={novel?.story_structure ?? "three_act"}
          onClose={() => {
            structureGuard.close();
            setDirty(false);
          }}
          onCancel={() => {
            // Cancel reverts the local structure to the original + closes the guard.
            if (novel) setLocalStoryStructure(novel.story_structure);
            structureGuard.close();
            setDirty(false);
          }}
        />
      )}
    </div>
  );
}
