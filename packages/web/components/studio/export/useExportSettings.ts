"use client";

import { useCallback, useEffect, useState } from "react";
import type { EpubOptions, ExportFormat, ExportOptions, PdfOptions } from "@/types";

/** localStorage key for the remembered export settings ("remembered for next time"). */
const STORAGE_KEY = "narrare.export.options";

/** PDF defaults mirror NarrareRomanConfig (drop_caps OFF — ADR-081 D5). */
const DEFAULT_PDF_OPTIONS: PdfOptions = {
  paper_size: "b-format-129x198",
  margins: null,
  body_size_pt: 11,
  leading_ratio: 1.2,
  drop_caps: false,
  include_toc: true,
};

const DEFAULT_EPUB_OPTIONS: EpubOptions = { cover_image_path: null, css: null };

/** Build a fully-populated options object for a given format. */
export function defaultExportOptions(format: ExportFormat): ExportOptions {
  return {
    format,
    volume_id: null,
    include_front_matter: true,
    include_back_matter: true,
    include_summaries: false,
    include_character_list: false,
    include_location_glossary: false,
    pdf_options: { ...DEFAULT_PDF_OPTIONS },
    epub_options: { ...DEFAULT_EPUB_OPTIONS },
    markdown_options: { chapter_heading_level: 1, include_front_matter: true },
  };
}

/**
 * useExportSettings — persists the user's export options in localStorage so the
 * choice survives reloads ("Remember settings for next time", IO-001 §6).
 *
 * Read in a useEffect (not a lazy initializer) to avoid SSR/hydration
 * mismatches — the standard Next.js client-component localStorage pattern
 * (mirrors usePromptEditorMode). A corrupt payload falls back to the defaults
 * rather than crashing the panel.
 */
export function useExportSettings(): {
  readonly options: ExportOptions;
  readonly setOptions: (next: ExportOptions) => void;
} {
  const [options, setOptionsState] = useState<ExportOptions>(() => defaultExportOptions("pdf"));

  // Sync from localStorage on mount (SSR-safe — only runs in the browser).
  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as ExportOptions;
        // Rehydrate into a fully-populated object so a stored payload that
        // predates a new option field still has a sensible default.
        setOptionsState({ ...defaultExportOptions(parsed.format), ...parsed });
      }
    } catch {
      // Corrupt / unavailable storage — keep the in-memory defaults.
    }
  }, []);

  const setOptions = useCallback((next: ExportOptions): void => {
    setOptionsState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      // Ignore persistence failures — in-memory state still updates.
    }
  }, []);

  return { options, setOptions };
}
