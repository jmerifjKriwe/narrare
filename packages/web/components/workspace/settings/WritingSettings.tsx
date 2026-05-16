"use client";

import { Target } from "lucide-react";
import { useState } from "react";
import { useTranslations } from "next-intl";

export function WritingSettings() {
  const t = useTranslations("settings");
  const [dailyGoal, setDailyGoal] = useState(1000);
  const [totalGoal, setTotalGoal] = useState(80000);

  // Hardcoded current words for demo — will be persisted later
  const currentWords = 1825;
  const progressPercent = Math.min(Math.round((currentWords / totalGoal) * 100), 100);

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-2xl mb-2">{t("writing")}</h2>
        <p className="text-sm text-muted-foreground">
          {t("writingDescription")}
        </p>
      </div>

      <div className="space-y-4">
        {/* Daily writing goal card */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center flex-shrink-0">
              <Target className="w-5 h-5" />
            </div>
            <div className="flex-1">
              <h3 className="mb-1 font-medium">{t("dailyGoal")}</h3>
              <p className="text-sm text-muted-foreground mb-4">
                {t("dailyGoalDescription")}
              </p>
              <div className="flex items-center gap-3">
                <input
                  type="number"
                  value={dailyGoal}
                  onChange={(e) => setDailyGoal(Number(e.target.value))}
                  className="w-32 px-4 py-2 bg-background border border-border rounded-md focus:ring-1 focus:ring-ring transition-shadow"
                  min={0}
                  step={100}
                  aria-label={t("dailyGoal")}
                />
                <span className="text-muted-foreground">{t("wordsPerDay")}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Project progress card */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center flex-shrink-0">
              <Target className="w-5 h-5" />
            </div>
            <div className="flex-1">
              <h3 className="mb-1 font-medium">{t("projectProgress")}</h3>
              <p className="text-sm text-muted-foreground mb-4">
                {t("projectProgressDescription")}
              </p>
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <input
                    type="number"
                    value={totalGoal}
                    onChange={(e) => setTotalGoal(Number(e.target.value))}
                    className="w-32 px-4 py-2 bg-background border border-border rounded-md focus:ring-1 focus:ring-ring transition-shadow"
                    min={0}
                    step={1000}
                    aria-label={t("projectProgress")}
                  />
                  <span className="text-muted-foreground">{t("wordsTotal")}</span>
                </div>
                <div className="mt-4">
                  <div className="flex items-center justify-between text-sm mb-2">
                    <span className="text-muted-foreground">{t("progress")}</span>
                    <span className="font-medium">
                      {currentWords.toLocaleString()} / {totalGoal.toLocaleString()} ({progressPercent}%)
                    </span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary transition-all"
                      style={{ width: `${progressPercent}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
