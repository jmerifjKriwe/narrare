"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { promptsApi } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import type { PromptInfo, UpdateInfo } from "@/types";
import { PromptEditor } from "./PromptEditor";

const PROMPT_CATEGORIES = ["generation", "writing", "analysis", "kb"] as const;

interface GroupedPrompts {
  [category: string]: PromptInfo[];
}

/** Derive a readable display name from prompt metadata. */
function formatPromptName(prompt: PromptInfo): string {
  // If the API provides a good human-readable name, use it directly.
  // A name is considered "good" if it differs from the prompt_id and does not
  // look like a raw path (compact slashes without surrounding spaces).
  if (prompt.name && prompt.name !== prompt.prompt_id && !/[^ ]\/[^ ]/.test(prompt.name)) {
    return prompt.name;
  }

  // Otherwise derive from prompt_id like "generation/names" → "Name Generation"
  const parts = prompt.prompt_id.split("/");
  const mode = parts[parts.length - 1] || prompt.prompt_id;

  const languageNames: Record<string, string> = {
    en: "English",
    de: "German",
    fr: "French",
  };
  const langSuffix = languageNames[prompt.language]
    ? ` (${languageNames[prompt.language]})`
    : prompt.language
      ? ` (${prompt.language})`
      : "";

  const modeNames: Record<string, string> = {
    names: "Name Generation",
    titles: "Title Generation",
    general: "General Generation",
  };
  const readableMode = modeNames[mode] || mode.charAt(0).toUpperCase() + mode.slice(1);

  return `${readableMode}${langSuffix}`;
}

export function PromptSettings() {
  const t = useTranslations("settings");
  const tAi = useTranslations("settings-ai.categories");
  const [selectedPromptId, setSelectedPromptId] = useState<string | null>(null);
  const [filterCategory, setFilterCategory] = useState<string>("all");

  const {
    data: prompts,
    isLoading: promptsLoading,
    error: promptsError,
  } = useQuery({
    queryKey: ["prompts", filterCategory === "all" ? undefined : filterCategory],
    queryFn: () => promptsApi.list(filterCategory === "all" ? undefined : filterCategory),
  });

  const { data: updates } = useQuery({
    queryKey: ["prompts-updates"],
    queryFn: () => promptsApi.updates(),
  });

  const updateMap = new Map<string, UpdateInfo>((updates ?? []).map((u) => [u.prompt_id, u]));

  const groupedPrompts: GroupedPrompts = {};
  if (prompts) {
    for (const prompt of prompts) {
      const cat = prompt.category;
      if (!groupedPrompts[cat]) groupedPrompts[cat] = [];
      groupedPrompts[cat].push(prompt);
    }
  }

  if (selectedPromptId) {
    return (
      <PromptEditor
        promptId={selectedPromptId}
        hasUpdate={updateMap.has(selectedPromptId)}
        onBack={() => setSelectedPromptId(null)}
      />
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-[var(--color-text-primary)]">{t("aiPrompts")}</h2>
      </div>

      {/* Category filter */}
      <div className="flex gap-2 flex-wrap">
        <button
          type="button"
          onClick={() => setFilterCategory("all")}
          className={cn(
            "px-3 py-1.5 rounded-lg text-[0.8125rem] font-medium transition-colors",
            filterCategory === "all"
              ? "bg-[var(--color-accent)] text-white"
              : "bg-[var(--color-bg-secondary)] text-[var(--color-text-secondary)] hover:bg-[var(--color-accent-light)]",
          )}
        >
          {t("allCategories")}
        </button>
        {PROMPT_CATEGORIES.map((cat) => (
          <button
            key={cat}
            type="button"
            onClick={() => setFilterCategory(cat)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-[0.8125rem] font-medium transition-colors",
              filterCategory === cat
                ? "bg-[var(--color-accent)] text-white"
                : "bg-[var(--color-bg-secondary)] text-[var(--color-text-secondary)] hover:bg-[var(--color-accent-light)]",
            )}
          >
            {tAi(cat === "kb" ? "knowledgeBase" : cat)}
          </button>
        ))}
      </div>

      {promptsLoading && (
        <p className="text-[var(--color-text-tertiary)] text-[0.875rem]">{t("loadingPrompts")}</p>
      )}

      {promptsError && (
        <div
          className="bg-[var(--color-error)]/10 text-[var(--color-error)] rounded-lg p-3 text-[0.875rem]"
          role="alert"
        >
          {t("loadFailed")}
        </div>
      )}

      {prompts && prompts.length === 0 && (
        <p className="text-[var(--color-text-tertiary)] text-[0.875rem]">{t("noPromptsFound")}</p>
      )}

      {/* Grouped prompt list */}
      {Object.entries(groupedPrompts).map(([category, categoryPrompts]) => (
        <div key={category} className="flex flex-col gap-2">
          <h3 className="text-[0.75rem] font-semibold uppercase tracking-[0.15em] text-[var(--color-text-tertiary)]">
            {tAi(category === "kb" ? "knowledgeBase" : category)}
          </h3>
          <ul className="flex flex-col gap-1">
            {categoryPrompts.map((prompt) => {
              const hasUpdate = updateMap.has(prompt.prompt_id);
              return (
                <li key={prompt.prompt_id}>
                  <button
                    type="button"
                    onClick={() => setSelectedPromptId(prompt.prompt_id)}
                    className={cn(
                      "w-full flex items-center justify-between px-4 py-3 rounded-xl text-left transition-colors",
                      "hover:bg-[var(--color-accent-light)]/30",
                      prompt.is_overridden && "border border-[var(--color-accent)]/20",
                    )}
                  >
                    <div className="flex flex-col gap-0.5">
                      <span className="text-[0.9375rem] font-medium text-[var(--color-text-primary)]">
                        {formatPromptName(prompt)}
                      </span>
                      <span className="text-[0.75rem] text-[var(--color-text-tertiary)]">
                        {prompt.is_overridden ? t("sourceOverride") : t("sourceBundled")}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      {hasUpdate && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[0.6875rem] font-semibold bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400">
                          {t("updateAvailable")}
                        </span>
                      )}
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}
