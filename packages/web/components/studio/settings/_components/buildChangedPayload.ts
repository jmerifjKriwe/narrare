import type { Novel } from "@/types";

/** Form field state used by NovelDetailsTab and its sub-components. */
export interface NovelFormState {
  title: string;
  author: string;
  writingLanguage: string;
  genre: string;
  tone: string;
  storyStructure: string;
  logline: string;
  synopsis: string;
}

/**
 * Compare current form state against the original novel data and return
 * a changed-fields-only payload suitable for the update API.
 */
export function buildChangedPayload(form: NovelFormState, novel: Novel): Partial<Novel> {
  const payload: Partial<Novel> = {};
  if (form.title !== novel.title) payload.title = form.title;
  if (form.author !== novel.author) payload.author = form.author;
  if (form.writingLanguage !== novel.writing_language)
    payload.writing_language = form.writingLanguage;
  if (form.genre !== novel.genre) payload.genre = form.genre;
  if (form.tone !== novel.tone) payload.tone = form.tone;
  if (form.storyStructure !== novel.story_structure) payload.story_structure = form.storyStructure;
  if (form.logline !== novel.logline) payload.logline = form.logline;
  if (form.synopsis !== novel.synopsis) payload.synopsis = form.synopsis;
  return payload;
}
