"use client";

/**
 * DailyGoalCard — the daily-goal motivator card (STATS-001). Deliberately
 * stateless-local (see the WritingGoalsTab module doc): v1 ships no
 * daily-goal storage, so this stays an unpersisted motivator input.
 * Extracted whole (card + input) to keep the persisted-goal flow in
 * WritingGoalsTab readable (RULE-04).
 */

import { Target } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

export function DailyGoalCard() {
  const t = useTranslations("studio");

  return (
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
        <DailyGoalInput />
      </div>
    </div>
  );
}

/**
 * Daily-goal input — deliberately stateless-local: v1 ships no daily-goal
 * storage, so this stays an unpersisted motivator input.
 */
function DailyGoalInput() {
  const t = useTranslations("studio");
  const [dailyGoal, setDailyGoal] = useState(1000);

  return (
    <div className="flex items-center gap-2">
      <input
        type="number"
        value={dailyGoal}
        onChange={(e) => setDailyGoal(Number(e.target.value))}
        min={0}
        step={100}
        aria-label={t("settings.writing.dailyGoal")}
        className="w-32 px-4 py-2 bg-background border border-border rounded-md text-sm text-right"
      />
      <span className="text-sm text-muted-foreground">{t("settings.writing.wordsPerDay")}</span>
    </div>
  );
}
