"use client";

import type { UseFormRegister } from "react-hook-form";
import { GENRE_SUGGESTIONS } from "@/lib/constants/genres";

const GENRE_DATALIST_ID = "genre-suggestions";

/** Form field values shared with WizardStep3. */
export interface NovelMetadataFormValues {
  title: string;
  author: string;
  genre: string;
  writing_language: string;
  logline: string;
  story_structure: string;
  tone: string;
}

interface NovelMetadataFieldsProps {
  register: UseFormRegister<NovelMetadataFormValues>;
  structureOptions: { value: string; label: string }[];
  toneOptions: { value: string; label: string }[];
  translations: {
    novelTitle: string;
    novelTitlePlaceholder: string;
    author: string;
    authorPlaceholder: string;
    genre: string;
    genrePlaceholder: string;
    writingLanguage: string;
    writingLanguagePlaceholder: string;
    logline: string;
    loglinePlaceholder: string;
    structure: string;
    tone: string;
  };
  titleError?: string;
}

export function NovelMetadataFields({
  register,
  structureOptions,
  toneOptions,
  translations: t,
  titleError,
}: NovelMetadataFieldsProps) {
  return (
    <>
      <div>
        <label htmlFor="novel_title" className="block text-sm font-medium mb-1.5">
          {t.novelTitle}
        </label>
        <input
          id="novel_title"
          type="text"
          {...register("title")}
          placeholder={t.novelTitlePlaceholder}
          className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
        />
        {titleError && <p className="text-sm text-destructive mt-1">{titleError}</p>}
      </div>

      <div>
        <label htmlFor="author" className="block text-sm font-medium mb-1.5">
          {t.author}
        </label>
        <input
          id="author"
          type="text"
          {...register("author")}
          placeholder={t.authorPlaceholder}
          className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
        />
      </div>

      <div>
        <label htmlFor="genre" className="block text-sm font-medium mb-1.5">
          {t.genre}
        </label>
        <input
          id="genre"
          type="text"
          list={GENRE_DATALIST_ID}
          {...register("genre")}
          placeholder={t.genrePlaceholder}
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
          {t.writingLanguage}
        </label>
        <input
          id="writing_language"
          type="text"
          {...register("writing_language")}
          placeholder={t.writingLanguagePlaceholder}
          className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
        />
      </div>

      <div>
        <label htmlFor="logline" className="block text-sm font-medium mb-1.5">
          {t.logline}
        </label>
        <input
          id="logline"
          type="text"
          {...register("logline")}
          placeholder={t.loglinePlaceholder}
          className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
        />
      </div>

      <div>
        <label htmlFor="story_structure" className="block text-sm font-medium mb-1.5">
          {t.structure}
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
          {t.tone}
        </label>
        <select
          id="tone"
          {...register("tone")}
          className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
        >
          {toneOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
    </>
  );
}
