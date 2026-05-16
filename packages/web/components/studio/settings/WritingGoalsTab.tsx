"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2, Target } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { chaptersApi } from "@/lib/api/client";

interface WritingGoalsTabProps {
  novelId: string;
}

export function WritingGoalsTab({ novelId }: WritingGoalsTabProps) {
  const t = useTranslations("studio");
  const [dailyGoal, setDailyGoal] = useState(1000);
  const [totalGoal, setTotalGoal] = useState(80000);

  // Fetch chapters to compute total word count
  const { data: chapters = [], isLoading } = useQuery({
    queryKey: ["novels", novelId, "chapters"],
    queryFn: () => chaptersApi.list(novelId),
  });

  const currentWords = chapters.reduce((sum, ch) => sum + ch.word_count, 0);
  const progressPercent = Math.min(Math.round((currentWords / totalGoal) * 100), 100);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-medium mb-1">{t("settings.writing.title")}</h2>
        <p className="text-sm text-muted-foreground">{t("settings.writing.description")}</p>
      </div>
      <div className="space-y-4">
        {/* Daily goal */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
                <Target className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-medium">{t("settings.writing.dailyGoal")}</h3>
                <p className="text-sm text-muted-foreground">
                  {t("settings.writing.dailyGoalDescription")}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="number"
                value={dailyGoal}
                onChange={(e) => setDailyGoal(Number(e.target.value))}
                min={0}
                step={100}
                className="w-32 px-4 py-2 bg-background border border-border rounded-md text-sm text-right"
              />
              <span className="text-sm text-muted-foreground">
                {t("settings.writing.wordsPerDay")}
              </span>
            </div>
          </div>
        </div>

        {/* Project progress */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="mb-4">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
                <Target className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-medium">{t("settings.writing.projectProgress")}</h3>
                <p className="text-sm text-muted-foreground">
                  {t("settings.writing.projectProgressDescription")}
                </p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-4 mb-4">
            <div className="flex items-center gap-2">
              <input
                type="number"
                value={totalGoal}
                onChange={(e) => setTotalGoal(Number(e.target.value))}
                min={0}
                step={1000}
                className="w-32 px-4 py-2 bg-background border border-border rounded-md text-sm text-right"
              />
              <span className="text-sm text-muted-foreground">
                {t("settings.writing.wordsTotal")}
              </span>
            </div>
          </div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-muted-foreground">{t("settings.writing.progress")}</span>
            <span className="text-sm font-medium">
              {currentWords.toLocaleString()} / {totalGoal.toLocaleString()} ({progressPercent}%)
            </span>
          </div>
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-primary rounded-full transition-all"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
