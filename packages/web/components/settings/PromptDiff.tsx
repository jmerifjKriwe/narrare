"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/Button";
import { promptsApi } from "@/lib/api/client";
import { cn } from "@/lib/utils";

interface PromptDiffProps {
  readonly promptId: string;
  readonly onBack: () => void;
  readonly onResolved: () => void;
}

interface DiffLine {
  type: "same" | "added" | "removed";
  content: string;
}

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

export function PromptDiff({ promptId, onBack, onResolved }: PromptDiffProps) {
  const t = useTranslations("settings");
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
      <div className="flex flex-col gap-4">
        <p className="text-muted-foreground text-[0.875rem]">{t("loadingPrompt")}</p>
      </div>
    );
  }

  if (error || !diffData) {
    return (
      <div className="flex flex-col gap-4">
        <div
          className="bg-destructive/10 text-destructive rounded-lg p-3 text-[0.875rem]"
          role="alert"
        >
          {t("loadFailed")}
        </div>
        <Button variant="secondary" onClick={onBack}>
          {t("back")}
        </Button>
      </div>
    );
  }

  const diffLines = computeDiffLines(diffData.override_content, diffData.bundled_content);

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-foreground">{t("diffTitle")}</h2>
      </div>

      {/* Side-by-side diff */}
      <div className="grid grid-cols-2 gap-4">
        {/* Override (left) */}
        <div className="flex flex-col gap-2">
          <h3 className="text-[0.75rem] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
            {t("yourVersion")}
          </h3>
          <div className="border border-border rounded-xl bg-secondary overflow-auto max-h-[500px]">
            {diffLines
              .filter((l) => l.type === "same" || l.type === "removed")
              .map((line) => (
                <div
                  key={`o-${line.type}-${line.content.slice(0, 60)}`}
                  className={cn(
                    "px-4 py-0.5 text-[0.8125rem] font-mono whitespace-pre-wrap",
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
        <div className="flex flex-col gap-2">
          <h3 className="text-[0.75rem] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
            {t("newDefault")}
          </h3>
          <div className="border border-border rounded-xl bg-secondary overflow-auto max-h-[500px]">
            {diffLines
              .filter((l) => l.type === "same" || l.type === "added")
              .map((line) => (
                <div
                  key={`b-${line.type}-${line.content.slice(0, 60)}`}
                  className={cn(
                    "px-4 py-0.5 text-[0.8125rem] font-mono whitespace-pre-wrap",
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
        <Button
          variant="secondary"
          onClick={() => keepMutation.mutate()}
          loading={keepMutation.isPending}
        >
          {t("keepMyVersion")}
        </Button>
        <Button onClick={() => acceptMutation.mutate()} loading={acceptMutation.isPending}>
          {t("acceptNewDefault")}
        </Button>
      </div>
    </div>
  );
}
