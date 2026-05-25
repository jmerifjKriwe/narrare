"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, FileText, Loader2, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { novelsApi, tonesApi } from "@/lib/api/client";
import { GENRE_SUGGESTIONS } from "@/lib/constants/genres";
import { BUNDLED_TONES } from "@/lib/constants/tones";
import type { CustomTone, Novel, StoryStructure } from "@/types";
import { StructureChangeDialog } from "../planning/StructureChangeDialog";

// --- Static option configs ---

const GENRE_DATALIST_ID = "novel-genre-suggestions";

const STRUCTURE_OPTIONS: { value: StoryStructure; labelKey: string }[] = [
  { value: "three_act", labelKey: "wizard.storyStructure.three_act" },
  { value: "five_act", labelKey: "wizard.storyStructure.five_act" },
  { value: "heros_journey", labelKey: "wizard.storyStructure.heros_journey" },
  { value: "save_the_cat", labelKey: "wizard.storyStructure.save_the_cat" },
  { value: "seven_point", labelKey: "wizard.storyStructure.seven_point" },
];

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

  // Structure change dialog state
  const [remapDialogOpen, setRemapDialogOpen] = useState(false);
  const [pendingStructure, setPendingStructure] = useState<string | null>(null);

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

  // Build a changed-fields-only payload by comparing original vs local
  function buildChangedPayload(): Partial<Novel> {
    if (!novel) return {};
    const payload: Partial<Novel> = {};
    if (localTitle !== novel.title) payload.title = localTitle;
    if (localAuthor !== novel.author) payload.author = localAuthor;
    if (localWritingLanguage !== novel.writing_language)
      payload.writing_language = localWritingLanguage;
    if (localGenre !== novel.genre) payload.genre = localGenre;
    if (localTone !== novel.tone) payload.tone = localTone;
    if (localStoryStructure !== novel.story_structure)
      payload.story_structure = localStoryStructure;
    if (localLogline !== novel.logline) payload.logline = localLogline;
    if (localSynopsis !== novel.synopsis) payload.synopsis = localSynopsis;
    return payload;
  }

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: (payload: Partial<Novel>) => novelsApi.update(novelId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["novels"] });
      setDirty(false);
    },
  });

  function handleSave() {
    const payload = buildChangedPayload();

    // Check if story structure changed — show remap dialog instead of direct save
    if (novel && payload.story_structure && payload.story_structure !== novel.story_structure) {
      // Save other fields first (excluding structure)
      const otherPayload = { ...payload };
      delete otherPayload.story_structure;
      if (Object.keys(otherPayload).length > 0) {
        saveMutation.mutate(otherPayload);
      }
      // Open remap dialog for the structure change
      setPendingStructure(payload.story_structure);
      setRemapDialogOpen(true);
      return;
    }

    if (Object.keys(payload).length > 0) {
      saveMutation.mutate(payload);
    }
  }

  // Field change handlers — all set dirty
  function handleTitleChange(value: string) {
    setLocalTitle(value);
    setDirty(true);
  }

  function handleAuthorChange(value: string) {
    setLocalAuthor(value);
    setDirty(true);
  }

  function handleWritingLanguageChange(value: string) {
    setLocalWritingLanguage(value);
    setDirty(true);
  }

  function handleGenreChange(value: string) {
    setLocalGenre(value);
    setDirty(true);
  }

  function handleToneChange(value: string) {
    setLocalTone(value);
    setDirty(true);
  }

  function handleStoryStructureChange(value: string) {
    setLocalStoryStructure(value);
    setDirty(true);
  }

  function handleLoglineChange(value: string) {
    setLocalLogline(value);
    setDirty(true);
  }

  function handleSynopsisChange(value: string) {
    setLocalSynopsis(value);
    setDirty(true);
  }

  // Remap dialog: cancel reverts local structure to original
  function handleRemapCancel() {
    if (novel) {
      setLocalStoryStructure(novel.story_structure);
    }
    setPendingStructure(null);
    setDirty(false);
  }

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
      <div className="mb-6">
        <h2 className="text-xl font-medium mb-1">{t("settings.novelDetailsSection.title")}</h2>
        <p className="text-sm text-muted-foreground">
          {t("settings.novelDetailsSection.description")}
        </p>
      </div>

      <div className="space-y-4">
        {/* Basic Info card */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
              <BookOpen className="w-6 h-6" />
            </div>
            <div>
              <h3 className="font-medium">{t("settings.novelDetailsSection.basicInfo")}</h3>
              <p className="text-sm text-muted-foreground">
                {t("settings.novelDetailsSection.basicInfoDescription")}
              </p>
            </div>
          </div>
          <div className="ml-15 space-y-4">
            <div>
              <label htmlFor="novel-title" className="text-sm font-medium mb-1 block">
                {t("settings.novelDetailsSection.titleField")}
              </label>
              <p className="text-xs text-muted-foreground mb-2">
                {t("settings.novelDetailsSection.titleFieldDescription")}
              </p>
              <input
                id="novel-title"
                type="text"
                value={localTitle}
                onChange={(e) => handleTitleChange(e.target.value)}
                className="w-full max-w-md px-4 py-2 bg-background border border-border rounded-md text-sm"
              />
            </div>
            <div>
              <label htmlFor="novel-author" className="text-sm font-medium mb-1 block">
                {t("settings.novelDetailsSection.authorField")}
              </label>
              <p className="text-xs text-muted-foreground mb-2">
                {t("settings.novelDetailsSection.authorFieldDescription")}
              </p>
              <input
                id="novel-author"
                type="text"
                value={localAuthor}
                onChange={(e) => handleAuthorChange(e.target.value)}
                className="w-full max-w-md px-4 py-2 bg-background border border-border rounded-md text-sm"
              />
            </div>
            <div>
              <label htmlFor="novel-language" className="text-sm font-medium mb-1 block">
                {t("settings.novelDetailsSection.languageField")}
              </label>
              <p className="text-xs text-muted-foreground mb-2">
                {t("settings.novelDetailsSection.languageFieldDescription")}
              </p>
              <input
                id="novel-language"
                type="text"
                value={localWritingLanguage}
                onChange={(e) => handleWritingLanguageChange(e.target.value)}
                maxLength={100}
                className="w-full max-w-md px-4 py-2 bg-background border border-border rounded-md text-sm"
              />
            </div>
          </div>
        </div>

        {/* Story card */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
              <Sparkles className="w-6 h-6" />
            </div>
            <div>
              <h3 className="font-medium">{t("settings.novelDetailsSection.storyCard")}</h3>
              <p className="text-sm text-muted-foreground">
                {t("settings.novelDetailsSection.storyCardDescription")}
              </p>
            </div>
          </div>
          <div className="ml-15 space-y-4">
            <div>
              <label htmlFor="novel-genre" className="text-sm font-medium mb-1 block">
                {t("settings.novelDetailsSection.genreField")}
              </label>
              <p className="text-xs text-muted-foreground mb-2">
                {t("settings.novelDetailsSection.genreFieldDescription")}
              </p>
              <input
                id="novel-genre"
                type="text"
                list={GENRE_DATALIST_ID}
                value={localGenre}
                onChange={(e) => handleGenreChange(e.target.value)}
                className="w-full max-w-md px-4 py-2 bg-background border border-border rounded-md text-sm"
              />
              <datalist id={GENRE_DATALIST_ID}>
                {GENRE_SUGGESTIONS.map((suggestion) => (
                  <option key={suggestion} value={suggestion} />
                ))}
              </datalist>
            </div>
            <div>
              <label htmlFor="novel-tone" className="text-sm font-medium mb-1 block">
                {t("settings.novelDetailsSection.toneField")}
              </label>
              <p className="text-xs text-muted-foreground mb-2">
                {t("settings.novelDetailsSection.toneFieldDescription")}
              </p>
              <select
                id="novel-tone"
                value={localTone}
                onChange={(e) => handleToneChange(e.target.value)}
                className="px-4 py-2 bg-background border border-border rounded-md text-sm"
              >
                <option value="">—</option>
                <optgroup label={t("tones.bundled")}>
                  {BUNDLED_TONES.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {t(opt.label)}
                    </option>
                  ))}
                </optgroup>
                {customTones && customTones.length > 0 && (
                  <optgroup label={t("tones.custom")}>
                    {customTones.map((tone: CustomTone) => (
                      <option key={tone.id} value={`custom:${tone.id}`}>
                        {tone.name}
                      </option>
                    ))}
                  </optgroup>
                )}
              </select>
            </div>
            <div>
              <label htmlFor="novel-story-structure" className="text-sm font-medium mb-1 block">
                {t("settings.novelDetailsSection.storyStructureField")}
              </label>
              <p className="text-xs text-muted-foreground mb-2">
                {t("settings.novelDetailsSection.storyStructureFieldDescription")}
              </p>
              <select
                id="novel-story-structure"
                value={localStoryStructure}
                onChange={(e) => handleStoryStructureChange(e.target.value)}
                className="px-4 py-2 bg-background border border-border rounded-md text-sm"
              >
                {STRUCTURE_OPTIONS.map(({ value, labelKey }) => (
                  <option key={value} value={value}>
                    {t(labelKey)}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Summary card */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
              <FileText className="w-6 h-6" />
            </div>
            <div>
              <h3 className="font-medium">{t("settings.novelDetailsSection.summaryCard")}</h3>
              <p className="text-sm text-muted-foreground">
                {t("settings.novelDetailsSection.summaryCardDescription")}
              </p>
            </div>
          </div>
          <div className="ml-15 space-y-4">
            <div>
              <label htmlFor="novel-logline" className="text-sm font-medium mb-1 block">
                {t("settings.novelDetailsSection.loglineField")}
              </label>
              <p className="text-xs text-muted-foreground mb-2">
                {t("settings.novelDetailsSection.loglineFieldDescription")}
              </p>
              <input
                id="novel-logline"
                type="text"
                value={localLogline}
                onChange={(e) => handleLoglineChange(e.target.value)}
                className="w-full max-w-md px-4 py-2 bg-background border border-border rounded-md text-sm"
              />
            </div>
            <div>
              <label htmlFor="novel-synopsis" className="text-sm font-medium mb-1 block">
                {t("settings.novelDetailsSection.synopsisField")}
              </label>
              <p className="text-xs text-muted-foreground mb-2">
                {t("settings.novelDetailsSection.synopsisFieldDescription")}
              </p>
              <textarea
                id="novel-synopsis"
                value={localSynopsis}
                onChange={(e) => handleSynopsisChange(e.target.value)}
                rows={6}
                className="w-full max-w-lg px-4 py-2 bg-background border border-border rounded-md text-sm resize-y"
              />
            </div>
          </div>
        </div>

        {/* Error message */}
        {saveMutation.isError && (
          <div className="text-sm text-destructive">
            {t("settings.novelDetailsSection.saveError")}
          </div>
        )}

        {/* Save button */}
        {dirty && (
          <div className="flex justify-end">
            <button
              type="button"
              onClick={handleSave}
              disabled={saveMutation.isPending}
              className="px-6 py-2.5 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity shadow-sm text-sm disabled:opacity-50"
            >
              {saveMutation.isPending ? t("settings.ai.loading") : t("settings.ai.save")}
            </button>
          </div>
        )}
      </div>

      {/* Structure Change Dialog */}
      {pendingStructure && (
        <StructureChangeDialog
          open={remapDialogOpen}
          novelId={novelId}
          newStructure={pendingStructure}
          currentStructure={novel?.story_structure ?? "three_act"}
          onClose={() => {
            setRemapDialogOpen(false);
            setPendingStructure(null);
            setDirty(false);
          }}
          onCancel={handleRemapCancel}
        />
      )}
    </div>
  );
}
