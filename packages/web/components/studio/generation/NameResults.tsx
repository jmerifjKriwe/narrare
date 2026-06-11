"use client";

import { useTranslations } from "next-intl";
import { useCallback, useState } from "react";
import type { KBEntityType } from "@/lib/api/kb";
import { kbApi } from "@/lib/api/kb";
import { cn } from "@/lib/utils";
import type { GeneratedName, NameGenerateResponse } from "@/types";

/** Per-name save state tracked in a record keyed by name. */
type NameSaveState = "idle" | "saving" | "saved" | "error";

interface NameResultsProps {
  readonly results: NameGenerateResponse | null;
  readonly isLoading: boolean;
  readonly novelId: string;
  readonly nameType: string;
}

/** Map generation name_type to KB entity_type. */
function toEntityType(nameType: string): KBEntityType {
  switch (nameType) {
    case "character":
      return "character";
    case "place":
      return "location";
    case "organization":
      return "faction";
    case "item":
      return "object";
    default:
      return "concept";
  }
}

export function NameResults({ results, isLoading, novelId, nameType }: NameResultsProps) {
  const t = useTranslations("studio");
  const [saveStates, setSaveStates] = useState<Record<string, NameSaveState>>({});

  const handleSaveToKb = useCallback(
    async (generated: GeneratedName) => {
      const name = generated.name;
      // Prevent double-clicks while saving or already saved
      const current = saveStates[name];
      if (current === "saving" || current === "saved") return;

      setSaveStates((prev) => ({ ...prev, [name]: "saving" }));

      try {
        const metadata: Record<string, unknown> = {};
        if (generated.pronunciation) metadata.pronunciation = generated.pronunciation;
        if (generated.meaning) metadata.meaning = generated.meaning;
        if (generated.name_style) metadata.name_style = generated.name_style;

        await kbApi.createEntry(novelId, {
          entity_type: toEntityType(nameType),
          name,
          source: "name_generator",
          review_status: "approved",
          status: "draft",
          metadata: Object.keys(metadata).length > 0 ? metadata : undefined,
        });

        setSaveStates((prev) => ({ ...prev, [name]: "saved" }));

        // Reset to idle after 3 seconds so user could save again if needed
        setTimeout(() => {
          setSaveStates((prev) => ({ ...prev, [name]: "idle" }));
        }, 3000);
      } catch {
        setSaveStates((prev) => ({ ...prev, [name]: "error" }));
      }
    },
    [novelId, nameType, saveStates],
  );

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

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="text-[0.75rem] font-semibold uppercase tracking-[0.15em] text-muted-foreground">
          {t("generation.nameGenerator")} ({results.count})
        </h3>
      </div>

      <ul className="flex flex-col gap-2">
        {results.names.map((generated) => {
          const state = saveStates[generated.name] ?? "idle";

          return (
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
                onClick={() => handleSaveToKb(generated)}
                disabled={state === "saving" || state === "saved"}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-[0.75rem] font-medium transition-colors",
                  state === "saved" &&
                    "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
                  state === "error" && "bg-destructive/10 text-destructive",
                  state === "saving" &&
                    "bg-secondary text-muted-foreground opacity-50 cursor-not-allowed",
                  state === "idle" &&
                    "bg-secondary text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                )}
                aria-label={`${t("generation.saveToKb")}: ${generated.name}`}
              >
                {state === "saving" && t("generation.saving")}
                {state === "saved" && t("generation.saved")}
                {state === "error" && t("generation.saveError")}
                {state === "idle" && t("generation.saveToKb")}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
