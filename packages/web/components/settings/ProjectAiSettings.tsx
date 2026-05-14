"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { CategoryOverrides } from "@/components/settings/CategoryOverrides";
import { CustomTokenLimits } from "@/components/settings/CustomTokenLimits";
import { IntentOverrides } from "@/components/settings/IntentOverrides";
import { Button } from "@/components/ui/Button";
import { aiSettingsApi } from "@/lib/api/client";
import type {
  ModelOverride,
  ProjectAiSettings as ProjectAiSettingsType,
  TokenLimitOverride,
  UserProvider,
} from "@/types";

interface ProjectAiSettingsProps {
  readonly novelId: string;
  readonly providers: UserProvider[];
}

export function ProjectAiSettings({ novelId, providers }: ProjectAiSettingsProps) {
  const t = useTranslations("settings-ai.projectSettings");
  const [projectSettings, setProjectSettings] = useState<ProjectAiSettingsType | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const [categoryOverrides, setCategoryOverrides] = useState<Record<string, ModelOverride>>({});
  const [intentOverrides, setIntentOverrides] = useState<Record<string, ModelOverride>>({});
  const [tokenLimitOverrides, setTokenLimitOverrides] = useState<
    Record<string, TokenLimitOverride>
  >({});

  useEffect(() => {
    let cancelled = false;

    async function loadSettings() {
      setLoading(true);
      setError(null);
      try {
        const [project, user] = await Promise.all([
          aiSettingsApi.getProjectSettings(novelId),
          aiSettingsApi.getUserSettings(),
        ]);
        if (cancelled) return;
        setProjectSettings(project);
        void user; // Store for potential future use
        setCategoryOverrides(project.category_overrides ?? {});
        setIntentOverrides(project.intent_overrides ?? {});
        setTokenLimitOverrides(project.token_limit_overrides ?? {});
      } catch (e: unknown) {
        if (cancelled) return;
        const msg = e instanceof Error ? e.message : t("loadFailed");
        setError(msg);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadSettings();
    return () => {
      cancelled = true;
    };
  }, [novelId, t]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      const updated = await aiSettingsApi.updateProjectSettings(novelId, {
        category_overrides: categoryOverrides,
        intent_overrides: intentOverrides,
        token_limit_overrides: tokenLimitOverrides,
      });
      setProjectSettings(updated);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : t("saveFailed");
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <span className="text-[var(--color-text-tertiary)]">{t("loading")}</span>
      </div>
    );
  }

  if (error && !projectSettings) {
    return (
      <div className="flex flex-col items-center gap-3 py-12">
        <p className="text-[var(--color-error)]" role="alert">
          {error}
        </p>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => window.location.reload()}
        >
          {t("retry")}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-1">
          {t("title")}
        </h2>
        <p className="text-[0.875rem] text-[var(--color-text-secondary)]">{t("description")}</p>
      </div>

      <CategoryOverrides
        overrides={categoryOverrides}
        providers={providers}
        onChange={setCategoryOverrides}
        modelOptions={{}}
      />

      <IntentOverrides
        overrides={intentOverrides}
        providers={providers}
        onChange={setIntentOverrides}
        modelOptions={{}}
      />

      <CustomTokenLimits overrides={tokenLimitOverrides} onChange={setTokenLimitOverrides} />

      {error && (
        <div
          className="bg-[var(--color-error)]/10 text-[var(--color-error)] rounded-lg p-3 text-[0.875rem]"
          role="alert"
        >
          {error}
        </div>
      )}

      {success && (
        <div className="bg-green-50 text-green-700 rounded-lg p-3 text-[0.875rem]">
          {t("saveSuccess")}
        </div>
      )}

      <div className="flex justify-end pt-2">
        <Button type="button" onClick={handleSave} loading={saving}>
          {t("save")}
        </Button>
      </div>
    </div>
  );
}
