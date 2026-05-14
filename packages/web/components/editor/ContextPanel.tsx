"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { ProjectAiSettings } from "@/components/settings/ProjectAiSettings";
import { aiSettingsApi } from "@/lib/api/client";

interface ContextPanelProps {
  readonly novelId: string;
}

export function ContextPanel({ novelId }: ContextPanelProps) {
  const t = useTranslations("editor");

  const { data: providers = [] } = useQuery({
    queryKey: ["ai-providers"],
    queryFn: aiSettingsApi.listProviders,
  });

  return (
    <aside className="w-[var(--panel-width)] border-l border-[var(--color-border)] bg-[var(--color-surface)] flex flex-col shrink-0 overflow-hidden">
      <div className="px-4 py-3 border-b border-[var(--color-border)] shrink-0">
        <span className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">
          {t("contextPanel")}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto">
        <ProjectAiSettings novelId={novelId} providers={providers} />
      </div>
    </aside>
  );
}
