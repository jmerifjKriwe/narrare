"use client";

import { Sparkles } from "lucide-react";
import { GENRE_SUGGESTIONS } from "@/lib/constants/genres";
import { BUNDLED_TONES } from "@/lib/constants/tones";
import type { CustomTone, StoryStructure } from "@/types";

const GENRE_DATALIST_ID = "novel-genre-suggestions";

const STRUCTURE_OPTIONS: { value: StoryStructure; labelKey: string }[] = [
  { value: "three_act", labelKey: "wizard.storyStructure.three_act" },
  { value: "five_act", labelKey: "wizard.storyStructure.five_act" },
  { value: "heros_journey", labelKey: "wizard.storyStructure.heros_journey" },
  { value: "save_the_cat", labelKey: "wizard.storyStructure.save_the_cat" },
  { value: "seven_point", labelKey: "wizard.storyStructure.seven_point" },
];

interface StoryCardProps {
  localGenre: string;
  localTone: string;
  localStoryStructure: string;
  onGenreChange: (value: string) => void;
  onToneChange: (value: string) => void;
  onStoryStructureChange: (value: string) => void;
  customTones: CustomTone[] | undefined;
  t: (key: string) => string;
}

export function StoryCard({
  localGenre,
  localTone,
  localStoryStructure,
  onGenreChange,
  onToneChange,
  onStoryStructureChange,
  customTones,
  t,
}: StoryCardProps) {
  return (
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
            onChange={(e) => onGenreChange(e.target.value)}
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
            onChange={(e) => onToneChange(e.target.value)}
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
            onChange={(e) => onStoryStructureChange(e.target.value)}
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
  );
}
