"use client";

import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import type { NameGenerateResponse } from "@/types";

interface NameResultsProps {
  readonly results: NameGenerateResponse | null;
  readonly isLoading: boolean;
}

export function NameResults({ results, isLoading }: NameResultsProps) {
  const t = useTranslations("studio");

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="flex flex-col items-center gap-3">
          <span className="h-8 w-8 animate-spin rounded-full border-3 border-border border-t-primary" />
          <span className="text-muted-foreground text-[0.875rem]">
            {t("generation.generating")}
          </span>
        </div>
      </div>
    );
  }

  if (!results || results.names.length === 0) {
    return (
      <p className="text-muted-foreground text-[0.875rem] text-center py-8">
        {t("generation.noResults")}
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
        <h3 className="text-[0.75rem] font-semibold uppercase tracking-[0.15em] text-muted-foreground">
          {t("generation.nameGenerator")} ({results.count})
        </h3>
      </div>

      <ul className="flex flex-col gap-2">
        {results.names.map((generated) => (
          <li
            key={`${generated.name}-${generated.type}-${generated.name_style}`}
            className="flex items-center justify-between px-4 py-3 border border-border rounded-xl hover:bg-accent/10 transition-colors"
          >
            <div className="flex flex-col gap-0.5">
              <div className="flex items-center gap-2">
                <span className="text-[0.9375rem] font-medium text-foreground">
                  {generated.name}
                </span>
                {generated.is_duplicate && (
                  <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[0.625rem] font-semibold bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                    {t("generation.duplicate")}
                  </span>
                )}
              </div>
              <div className="flex gap-3 text-[0.75rem] text-muted-foreground">
                {generated.pronunciation && (
                  <span>
                    {t("generation.pronunciation")}: {generated.pronunciation}
                  </span>
                )}
                {generated.meaning && (
                  <span>
                    {t("generation.meaning")}: {generated.meaning}
                  </span>
                )}
              </div>
            </div>

            <button
              type="button"
              onClick={() => handleSaveToKb(generated.name)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-[0.75rem] font-medium transition-colors",
                "bg-secondary text-muted-foreground",
                "hover:bg-accent hover:text-accent-foreground",
              )}
              aria-label={`${t("generation.saveToKb")}: ${generated.name}`}
            >
              {t("generation.saveToKb")}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
