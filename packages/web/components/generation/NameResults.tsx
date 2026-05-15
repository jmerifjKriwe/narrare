"use client";

import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import type { NameGenerateResponse } from "@/types";

interface NameResultsProps {
  readonly results: NameGenerateResponse | null;
  readonly isLoading: boolean;
}

export function NameResults({ results, isLoading }: NameResultsProps) {
  const t = useTranslations("generation");

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="flex flex-col items-center gap-3">
          <span className="h-8 w-8 animate-spin rounded-full border-3 border-[var(--color-border)] border-t-[var(--color-accent)]" />
          <span className="text-[var(--color-text-tertiary)] text-[0.875rem]">
            {t("generating")}
          </span>
        </div>
      </div>
    );
  }

  if (!results) {
    return (
      <p className="text-[var(--color-text-tertiary)] text-[0.875rem] text-center py-8">
        {t("noResults")}
      </p>
    );
  }

  if (results.names.length === 0) {
    return (
      <p className="text-[var(--color-text-tertiary)] text-[0.875rem] text-center py-8">
        {t("noResults")}
      </p>
    );
  }

  const handleSaveToKb = (name: string) => {
    // TODO: Implement KB save when API is available
    // eslint-disable-next-line no-console
    console.log(`[TODO] Save to KB: ${name}`);
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="text-[0.75rem] font-semibold uppercase tracking-[0.15em] text-[var(--color-text-tertiary)]">
          {t("nameGenerator")} ({results.count})
        </h3>
      </div>

      <ul className="flex flex-col gap-2">
        {results.names.map((generated) => (
          <li
            key={`${generated.name}-${generated.type}-${generated.culture}`}
            className="flex items-center justify-between px-4 py-3 border border-[var(--color-border)] rounded-xl hover:bg-[var(--color-accent-light)]/10 transition-colors"
          >
            <div className="flex flex-col gap-0.5">
              <div className="flex items-center gap-2">
                <span className="text-[0.9375rem] font-medium text-[var(--color-text-primary)]">
                  {generated.name}
                </span>
                {generated.is_duplicate && (
                  <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[0.625rem] font-semibold bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                    {t("duplicate")}
                  </span>
                )}
              </div>
              <div className="flex gap-3 text-[0.75rem] text-[var(--color-text-tertiary)]">
                {generated.pronunciation && (
                  <span>
                    {t("pronunciation")}: {generated.pronunciation}
                  </span>
                )}
                {generated.meaning && (
                  <span>
                    {t("meaning")}: {generated.meaning}
                  </span>
                )}
              </div>
            </div>

            <button
              type="button"
              onClick={() => handleSaveToKb(generated.name)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-[0.75rem] font-medium transition-colors",
                "bg-[var(--color-bg-secondary)] text-[var(--color-text-secondary)]",
                "hover:bg-[var(--color-accent-light)] hover:text-[var(--color-accent)]",
              )}
              aria-label={`${t("saveToKb")}: ${generated.name}`}
            >
              {t("saveToKb")}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
