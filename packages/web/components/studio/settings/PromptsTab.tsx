"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { promptsApi } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import type { PromptInfo, UpdateInfo } from "@/types";
import { PromptEditor } from "./PromptEditor";

// --- Static config ---

const PROMPT_CATEGORIES = ["generation", "writing", "analysis", "kb"] as const;

// --- Helpers ---

function formatPromptName(prompt: PromptInfo): string {
  if (prompt.name && prompt.name !== prompt.prompt_id && !/[^ ]\/[^ ]/.test(prompt.name)) {
    return prompt.name;
  }

  const parts = prompt.prompt_id.split("/");
  const mode = parts[parts.length - 1] || prompt.prompt_id;

  const modeNames: Record<string, string> = {
    names: "Name Generation",
    titles: "Title Generation",
    general: "General Generation",
  };
  return modeNames[mode] || mode.charAt(0).toUpperCase() + mode.slice(1);
}

// --- Component ---

export function PromptsTab() {
  const t = useTranslations("studio");
  const [selectedPromptId, setSelectedPromptId] = useState<string | null>(null);
  const [filterCategory, setFilterCategory] = useState<string>("all");

  const { data: prompts, isLoading: promptsLoading } = useQuery({
    queryKey: ["prompts", filterCategory === "all" ? undefined : filterCategory],
    queryFn: () => promptsApi.list(filterCategory === "all" ? undefined : filterCategory),
  });

  const { data: updates } = useQuery({
    queryKey: ["prompts-updates"],
    queryFn: () => promptsApi.updates(),
  });

  const updateMap = new Map<string, UpdateInfo>((updates ?? []).map((u) => [u.prompt_id, u]));

  // Group prompts by category
  const groupedPrompts: Record<string, PromptInfo[]> = {};
  if (prompts) {
    for (const prompt of prompts) {
      const cat = prompt.category;
      if (!groupedPrompts[cat]) groupedPrompts[cat] = [];
      groupedPrompts[cat].push(prompt);
    }
  }

  // Editor view
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
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-medium mb-1">{t("settings.prompts.title")}</h2>
        <p className="text-sm text-muted-foreground">{t("settings.prompts.description")}</p>
      </div>

      <div className="space-y-4">
        {/* Category filter pills */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex gap-2 flex-wrap mb-4">
            <button
              type="button"
              onClick={() => setFilterCategory("all")}
              className={cn(
                "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                filterCategory === "all"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-accent",
              )}
            >
              {t("settings.prompts.allCategories")}
            </button>
            {PROMPT_CATEGORIES.map((cat) => (
              <button
                key={cat}
                type="button"
                onClick={() => setFilterCategory(cat)}
                className={cn(
                  "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                  filterCategory === cat
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-accent",
                )}
              >
                {t(`settings.prompts.${cat === "kb" ? "kb" : cat}`)}
              </button>
            ))}
          </div>

          {/* Loading state */}
          {promptsLoading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
              <span className="ml-2 text-sm text-muted-foreground">
                {t("settings.prompts.loadingPrompts")}
              </span>
            </div>
          )}

          {/* Empty state */}
          {!promptsLoading && prompts && prompts.length === 0 && (
            <div className="text-center py-8">
              <p className="text-sm text-muted-foreground">
                {t("settings.prompts.noPromptsFound")}
              </p>
            </div>
          )}

          {/* Grouped prompt list */}
          {Object.entries(groupedPrompts).map(([category, categoryPrompts]) => (
            <div key={category} className="mb-4 last:mb-0">
              <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-2">
                {t(`settings.prompts.${category === "kb" ? "kb" : category}`)}
              </h3>
              <div className="space-y-1">
                {categoryPrompts.map((prompt) => {
                  const hasUpdate = updateMap.has(prompt.prompt_id);
                  return (
                    <button
                      key={prompt.prompt_id}
                      type="button"
                      onClick={() => setSelectedPromptId(prompt.prompt_id)}
                      className={cn(
                        "w-full flex items-center justify-between px-4 py-3 rounded-md text-left transition-colors hover:bg-accent/30",
                        prompt.is_overridden && "border border-primary/20",
                      )}
                    >
                      <div>
                        <span className="text-sm font-medium">{formatPromptName(prompt)}</span>
                        <span className="block text-xs text-muted-foreground">
                          {prompt.is_overridden
                            ? t("settings.prompts.sourceOverride")
                            : t("settings.prompts.sourceBundled")}
                        </span>
                      </div>
                      {hasUpdate && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                          {t("settings.prompts.updateAvailable")}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
