"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { promptsApi } from "@/lib/api/client";
import { cn } from "@/lib/utils";

// --- Types ---

interface PromptDiffProps {
  readonly promptId: string;
  readonly onBack: () => void;
  readonly onResolved: () => void;
}

interface DiffLine {
  type: "same" | "added" | "removed";
  content: string;
}

// --- Helpers ---

function computeDiffLines(overrideContent: string, bundledContent: string): DiffLine[] {
  const overrideLines = overrideContent.split("\n");
  const bundledLines = bundledContent.split("\n");
  const maxLen = Math.max(overrideLines.length, bundledLines.length);
  const result: DiffLine[] = [];

  for (let i = 0; i < maxLen; i++) {
    const overrideLine = overrideLines[i];
    const bundledLine = bundledLines[i];

    if (overrideLine === undefined && bundledLine !== undefined) {
      result.push({ type: "added", content: bundledLine });
    } else if (overrideLine !== undefined && bundledLine === undefined) {
      result.push({ type: "removed", content: overrideLine });
    } else if (overrideLine !== bundledLine) {
      result.push({ type: "removed", content: overrideLine });
      result.push({ type: "added", content: bundledLine });
    } else {
      result.push({ type: "same", content: overrideLine });
    }
  }

  return result;
}

// --- Component ---

export function PromptDiff({ promptId, onBack, onResolved }: PromptDiffProps) {
  const t = useTranslations("studio");
  const queryClient = useQueryClient();

  const {
    data: diffData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["prompt-diff", promptId],
    queryFn: () => promptsApi.diff(promptId),
  });

  const keepMutation = useMutation({
    mutationFn: () => promptsApi.save(promptId, diffData?.override_content ?? ""),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prompts-updates"] });
      onResolved();
    },
  });

  const acceptMutation = useMutation({
    mutationFn: () => promptsApi.reset(promptId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prompts-updates"] });
      onResolved();
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
        <span className="ml-2 text-sm text-muted-foreground">
          {t("settings.prompts.loadingPrompt")}
        </span>
      </div>
    );
  }

  if (error || !diffData) {
    return (
      <div className="space-y-4">
        <div className="bg-destructive/10 text-destructive rounded-md p-3 text-sm" role="alert">
          {t("settings.prompts.loadFailed")}
        </div>
        <button
          type="button"
          onClick={onBack}
          className="px-4 py-2 bg-muted rounded-md hover:bg-accent transition-colors text-sm"
        >
          {t("settings.prompts.back")}
        </button>
      </div>
    );
  }

  const diffLines = computeDiffLines(diffData.override_content, diffData.bundled_content);

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-medium mb-1">{t("settings.prompts.diffTitle")}</h2>
      </div>

      <div className="space-y-4">
        {/* Side-by-side diff */}
        <div className="grid grid-cols-2 gap-4">
          {/* Override (left) */}
          <div className="space-y-2">
            <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              {t("settings.prompts.yourVersion")}
            </h3>
            <div className="border border-border rounded-md bg-background overflow-auto max-h-[500px]">
              {diffLines
                .filter((l) => l.type === "same" || l.type === "removed")
                .map((line) => (
                  <div
                    key={`o-${line.type}-${line.content.slice(0, 80)}`}
                    className={cn(
                      "px-4 py-0.5 text-xs font-mono whitespace-pre-wrap",
                      line.type === "removed" &&
                        "bg-red-100/50 text-red-800 dark:bg-red-900/20 dark:text-red-400",
                      line.type === "same" && "text-muted-foreground",
                    )}
                  >
                    {line.type === "removed" ? "- " : "  "}
                    {line.content}
                  </div>
                ))}
            </div>
          </div>

          {/* Bundled (right) */}
          <div className="space-y-2">
            <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              {t("settings.prompts.newDefault")}
            </h3>
            <div className="border border-border rounded-md bg-background overflow-auto max-h-[500px]">
              {diffLines
                .filter((l) => l.type === "same" || l.type === "added")
                .map((line) => (
                  <div
                    key={`b-${line.type}-${line.content.slice(0, 80)}`}
                    className={cn(
                      "px-4 py-0.5 text-xs font-mono whitespace-pre-wrap",
                      line.type === "added" &&
                        "bg-green-100/50 text-green-800 dark:bg-green-900/20 dark:text-green-400",
                      line.type === "same" && "text-muted-foreground",
                    )}
                  >
                    {line.type === "added" ? "+ " : "  "}
                    {line.content}
                  </div>
                ))}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={() => keepMutation.mutate()}
            disabled={keepMutation.isPending}
            className="px-6 py-2 bg-muted rounded-md hover:bg-accent transition-colors text-sm disabled:opacity-50"
          >
            {keepMutation.isPending
              ? t("settings.ai.loading")
              : t("settings.prompts.keepMyVersion")}
          </button>
          <button
            type="button"
            onClick={() => acceptMutation.mutate()}
            disabled={acceptMutation.isPending}
            className="px-6 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity text-sm disabled:opacity-50"
          >
            {acceptMutation.isPending
              ? t("settings.ai.loading")
              : t("settings.prompts.acceptNewDefault")}
          </button>
        </div>
      </div>
    </div>
  );
}
