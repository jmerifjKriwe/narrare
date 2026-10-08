"use client";

/**
 * WritingGoalsTab — novel writing-goal settings (STATS-001, spec E-4/E-5).
 *
 * The "Project progress" target persists as `ProjectSettings.writing_goals`
 * (`{"target_words": int | null}`, whole-object replace) through the shared
 * project-settings PATCH — the same query key and `settingsApi.updateProject`
 * mutation the SeriesVoiceOptOutCard uses, so both surfaces stay
 * cache-consistent and a save here also refreshes the analytics writing
 * report (its goal block is derived from this setting).
 *
 * READ side is defensive by contract: the GET returns the JSONB value as a
 * LOOSE `unknown` (a corrupt stored row must degrade, never fail the
 * render), so `parseTargetWords` (writingGoalRead.ts) narrows before any
 * `target_words` access — the FE mirror of the API's
 * `settings.writing_goals.parse_target_words`.
 *
 * WRITE side is strict: only a non-negative integer, or an empty field
 * (= explicit `null` = unset), reaches the API. Garbage drafts are blocked
 * at the surface with a validation message — the backend answers 422 to
 * anything else, so the two layers agree. Save state mirrors the sibling
 * settings fields (SaveFooter: dirty → save, saving → disabled, error →
 * inline message). The daily-goal card stays a local motivator — v1 ships
 * exactly one documented goal key (no daily-goal storage yet).
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Target } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { chaptersApi } from "@/lib/api/client";
import { settingsApi } from "@/lib/api/settings";
import type { WritingGoals } from "@/types";
import { SaveFooter } from "./_components/SaveFooter";
import { DailyGoalCard } from "./DailyGoalCard";
import { WritingGoalProgress } from "./WritingGoalProgress";
import { parseGoalDraft, parseTargetWords } from "./writingGoalRead";

/** Project-settings query key — shared with SeriesVoiceOptOutCard. */
const PROJECT_QUERY_KEY = (novelId: string) => ["settings", "novel", novelId] as const;

/** Analytics writing-report key prefix — a saved goal changes its goal block. */
const WRITING_REPORT_KEY = ["analytics", "writing"] as const;

interface WritingGoalsTabProps {
  novelId: string;
}

export function WritingGoalsTab({ novelId }: WritingGoalsTabProps) {
  const t = useTranslations("studio");
  const queryClient = useQueryClient();

  // Fetch chapters to compute total word count
  const { data: chapters = [], isLoading } = useQuery({
    queryKey: ["novels", novelId, "chapters"],
    queryFn: () => chaptersApi.list(novelId),
  });

  // Persisted goal — same project-settings query key the SeriesVoiceOptOutCard
  // reads, so saves from either surface invalidate one shared cache entry.
  const { data: projectSettings } = useQuery({
    queryKey: PROJECT_QUERY_KEY(novelId),
    queryFn: () => settingsApi.getProject(novelId),
  });

  // Defensively narrowed stored target (null = unset / corrupt row).
  const storedTarget = parseTargetWords(projectSettings?.writing_goals);

  // Input draft, synced from the stored goal until the user edits.
  const [draft, setDraft] = useState("");
  const [dirty, setDirty] = useState(false);
  const parsedDraft = parseGoalDraft(draft);
  const draftInvalid = parsedDraft === "invalid";

  useEffect(() => {
    if (!dirty) setDraft(storedTarget === null ? "" : String(storedTarget));
  }, [storedTarget, dirty]);

  // Goal save — whole-object replace; an explicit null unsets (backend
  // distinguishes null from omitted). Success invalidates the shared
  // settings entry AND the writing report (its goal block reads this row).
  const saveGoal = useMutation({
    mutationFn: (target_words: number | null) => {
      const payload: WritingGoals = { target_words };
      return settingsApi.updateProject(novelId, { writing_goals: payload });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PROJECT_QUERY_KEY(novelId) });
      void queryClient.invalidateQueries({ queryKey: WRITING_REPORT_KEY });
      setDirty(false);
    },
  });

  function handleSave() {
    // Defense-in-depth: the invalid state also hides the save button.
    if (parsedDraft === "invalid") return;
    saveGoal.mutate(parsedDraft);
  }

  const currentWords = chapters.reduce((sum, ch) => sum + ch.word_count, 0);
  // Progress reflects the target the user sees: the valid draft while
  // editing, otherwise the stored goal.
  const progressTarget = parsedDraft === "invalid" ? storedTarget : (parsedDraft ?? storedTarget);

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
        {/* Daily goal — local motivator (v1 has no daily-goal storage) */}
        <DailyGoalCard />

        {/* Project goal — persisted as ProjectSettings.writing_goals */}
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
          <div className="flex items-center gap-2">
            <label htmlFor="writing-goal-target" className="sr-only">
              {t("settings.writing.targetLabel")}
            </label>
            <input
              id="writing-goal-target"
              data-testid="writing-goal-target"
              type="text"
              inputMode="numeric"
              value={draft}
              onChange={(e) => {
                setDraft(e.target.value);
                setDirty(true);
              }}
              placeholder={t("settings.writing.targetPlaceholder")}
              aria-invalid={draftInvalid}
              className="w-32 px-4 py-2 bg-background border border-border rounded-md text-sm text-right disabled:opacity-50"
            />
            <span className="text-sm text-muted-foreground">
              {t("settings.writing.wordsTotal")}
            </span>
          </div>
          {draftInvalid ? (
            <p role="alert" className="mt-2 text-sm text-destructive">
              {t("settings.writing.targetInvalid")}
            </p>
          ) : null}
          <WritingGoalProgress currentWords={currentWords} target={progressTarget} />
          <div className="mt-4">
            <SaveFooter
              dirty={dirty && !draftInvalid}
              isSaving={saveGoal.isPending}
              isError={saveGoal.isError}
              onSave={handleSave}
              errorText={t("settings.writing.targetSaveError")}
              saveText={t("settings.ai.save")}
              loadingText={t("settings.ai.loading")}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
