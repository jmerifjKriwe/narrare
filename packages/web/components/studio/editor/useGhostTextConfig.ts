import type { useTranslations } from "next-intl";
import { useEffect, useMemo, useRef } from "react";
import { createSseSuggestionFetcher } from "@/lib/api/suggest";
import type { GhostTextOptions } from "./extensions/GhostText";
import { GhostText, simulateSuggestion } from "./extensions/GhostText";

type Translator = ReturnType<typeof useTranslations>;

interface UseGhostTextConfigParams {
  chapterId?: string;
  locale: string;
  t: Translator;
}

/**
 * Builds the {@link GhostText} extension configuration for the editor.
 *
 * Owns a single responsibility: wire the SSE suggestion fetcher (or the local
 * simulator when no chapter is bound) into the memoized GhostText options,
 * injecting localized hint/fetching/error strings so no hardcoded English
 * appears in ProseMirror DOM (CR-AUFG-07-10, ADR-043 Note 7).
 *
 * The fetcher is held in a ref so the extension config stays referentially
 * stable while still picking up chapter/locale changes.
 */
export function useGhostTextConfig({
  chapterId,
  locale,
  t,
}: UseGhostTextConfigParams): Partial<GhostTextOptions> {
  const fetchSuggestionRef = useRef<
    | ((params: { textBefore: string; textAfter: string; signal: AbortSignal }) => Promise<string>)
    | undefined
  >(undefined);

  useEffect(() => {
    fetchSuggestionRef.current = chapterId
      ? createSseSuggestionFetcher(chapterId, locale)
      : undefined;
  }, [chapterId, locale]);

  return useMemo<Partial<GhostTextOptions>>(
    () => ({
      fetchSuggestion: (params: { textBefore: string; textAfter: string; signal: AbortSignal }) =>
        fetchSuggestionRef.current?.(params) ?? simulateSuggestion(params),
      enabled: true,
      minChars: 5,
      suggestionDelay: 800,
      hintText: t("ghostText.hint"),
      // Localized fetching status — injected into the non-React extension via
      // options so no hardcoded English appears in ProseMirror DOM
      // (CR-AUFG-07-10, ADR-043 Note 7).
      fetchingStatusText: t("aiActions.aiThinking"),
      // Localized transient error text for non-AbortError fetch failures
      // (CR-AUFG-07-15). Low-noise, non-blocking, auto-clears after 4s.
      errorStatusText: t("ghostText.errorUnavailable"),
      errorStatusDurationMs: 4000,
    }),
    [t],
  );
}
