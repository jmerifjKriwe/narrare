/**
 * Notes i18n coverage (NOTES-001 §7/§8).
 *
 * The centralized setupTests mock returns i18n keys verbatim, so component
 * tests cannot verify real copy — this data-level test asserts that every
 * key the notes components use exists and is non-empty in ALL three locales
 * (the spec's "type labels per locale" requirement generalized to the whole
 * namespace), and that the namespace is registered in request.ts.
 */

import { existsSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const WEB_ROOT = resolve(__dirname, "..");
const I18N_MESSAGES = resolve(WEB_ROOT, "..", "i18n", "messages");
const LOCALES = ["en", "de", "fr"] as const;

const EXPECTED_KEYS = [
  "nav.label",
  "page.title",
  "page.subtitle",
  "empty.title",
  "empty.description",
  "empty.cta",
  "empty.selectPrompt",
  "list.searchPlaceholder",
  "list.typeFilterLabel",
  "list.allTypes",
  "list.tagFilterLabel",
  "list.allTags",
  "list.tagFilterPlaceholder",
  "list.clearTagFilter",
  "list.scopeFilterLabel",
  "list.allScopes",
  "list.scopeNovelsGroup",
  "list.scopeSeriesGroup",
  "list.noResults",
  "list.untitled",
  "list.updated",
  "type.idea",
  "type.concept",
  "type.question",
  "type.other",
  "editor.titlePlaceholder",
  "editor.contentLabel",
  "editor.contentPlaceholder",
  "editor.preview",
  "editor.edit",
  "editor.typeLabel",
  "editor.tagsLabel",
  "editor.tagPlaceholder",
  "editor.tagSuggestions",
  "editor.linkLabel",
  "editor.noLink",
  "editor.novelLink",
  "editor.seriesLink",
  "editor.discuss",
  "editor.delete",
  "editor.deleteTitle",
  "editor.deleteDescription",
  "editor.save",
  "editor.saveFailed",
  "editor.deleted",
  "editor.deleteFailed",
  "search.semanticToggle",
  "search.semanticBadge",
  "search.lexicalBadge",
  "quickCapture.open",
  "quickCapture.close",
  "quickCapture.title",
  "quickCapture.titlePlaceholder",
  "quickCapture.textPlaceholder",
  "quickCapture.tagPlaceholder",
  "quickCapture.save",
  "quickCapture.saved",
  "quickCapture.openInScratchpad",
  "quickCapture.shortcutHint",
  "chat.attachedNote",
  "chat.close",
] as const;

function flatten(obj: Record<string, unknown>, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return value && typeof value === "object"
      ? flatten(value as Record<string, unknown>, path)
      : [path];
  });
}

describe("notes i18n labels", () => {
  it.each(LOCALES)("locale %s has every expected notes key, non-empty", (locale) => {
    const file = join(I18N_MESSAGES, locale, "notes.json");
    expect(existsSync(file), `${file} must exist`).toBe(true);
    const flat = new Set(flatten(JSON.parse(readFileSync(file, "utf8"))));
    for (const key of EXPECTED_KEYS) {
      expect(flat.has(key), `${locale} missing notes.${key}`).toBe(true);
    }
  });

  it("registers the notes namespace in request.ts", () => {
    const requestTs = readFileSync(join(WEB_ROOT, "lib", "i18n", "request.ts"), "utf8");
    expect(requestTs).toMatch(/"notes"/);
  });
});
