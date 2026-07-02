"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useRef, useState } from "react";
import { AboutTab } from "@/components/studio/settings/AboutTab";
import { AiTab } from "@/components/studio/settings/AiTab";
import { BackgroundTasksPanel } from "@/components/studio/settings/BackgroundTasksPanel";
import { GeneralTab } from "@/components/studio/settings/GeneralTab";
import { KBTemplatesTab } from "@/components/studio/settings/KBTemplatesTab";
import { LearningTab } from "@/components/studio/settings/LearningTab";
import { NovelDetailsTab } from "@/components/studio/settings/NovelDetailsTab";
import { PromptsTab } from "@/components/studio/settings/PromptsTab";
import { SettingsSidebar } from "@/components/studio/settings/SettingsSidebar";
import { ShortcutsTab } from "@/components/studio/settings/ShortcutsTab";
import type { SettingsCategory } from "@/components/studio/settings/settings-view-config";
import { WritingGoalsTab } from "@/components/studio/settings/WritingGoalsTab";
import { settingsApi } from "@/lib/api/client";
import { searchParamsHref, setOptionalSearchParam } from "@/lib/url-state/searchParams";
import {
  DEFAULT_SETTINGS_CATEGORY,
  parseSettingsCategory,
  serializeSettingsCategory,
} from "./settings/settingsUrlState";

// --- Types ---

interface SettingsViewProps {
  novelId: string;
}

// --- Main Component ---

export function SettingsView({ novelId }: SettingsViewProps) {
  const t = useTranslations("studio");
  const queryClient = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const searchParamsSnapshot = searchParams.toString();
  const parsedCategory = useMemo(
    () => parseSettingsCategory(new URLSearchParams(searchParamsSnapshot).get("category")),
    [searchParamsSnapshot],
  );
  const [activeCategory, setActiveCategory] = useState<SettingsCategory>(parsedCategory);
  const previousSearchParamsSnapshotRef = useRef(searchParamsSnapshot);

  useEffect(() => {
    const currentParams = new URLSearchParams(searchParamsSnapshot);
    const currentValue = currentParams.get("category");
    const normalizedValue = serializeSettingsCategory(parsedCategory);
    const normalizedParams = setOptionalSearchParam(currentParams, "category", normalizedValue);
    const searchParamsChanged = previousSearchParamsSnapshotRef.current !== searchParamsSnapshot;
    previousSearchParamsSnapshotRef.current = searchParamsSnapshot;

    if (searchParamsChanged) setActiveCategory(parsedCategory);
    if (
      currentValue !== normalizedValue &&
      !(currentValue === null && parsedCategory === DEFAULT_SETTINGS_CATEGORY)
    ) {
      router.replace(searchParamsHref(pathname, normalizedParams), { scroll: false });
    }
  }, [parsedCategory, pathname, router, searchParamsSnapshot]);

  const handleCategoryChange = (category: SettingsCategory) => {
    setActiveCategory(category);
    const nextParams = setOptionalSearchParam(
      new URLSearchParams(searchParamsSnapshot),
      "category",
      serializeSettingsCategory(category),
    );
    router.push(searchParamsHref(pathname, nextParams), { scroll: false });
  };

  // User settings
  const { data: userSettings, isLoading: userSettingsLoading } = useQuery({
    queryKey: ["settings", "user"],
    queryFn: settingsApi.getUser,
  });

  // Mutation for updating user settings
  const updateSettingsMutation = useMutation({
    mutationFn: (payload: { display_name?: string; ui_language?: string }) =>
      settingsApi.updateUser(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "user"] });
    },
    onError: (err) => console.error("Failed to update user settings:", err),
  });

  // --- Content Sections ---

  function renderContent() {
    switch (activeCategory) {
      case "novel-details":
        return <NovelDetailsTab novelId={novelId} />;
      case "general":
        return (
          <GeneralTab
            displayName={userSettings?.display_name ?? ""}
            uiLanguage={userSettings?.ui_language ?? "en"}
            isLoading={userSettingsLoading}
            onSaveProfile={(payload) => updateSettingsMutation.mutate(payload)}
          />
        );
      case "writing":
        return <WritingGoalsTab novelId={novelId} />;
      case "ai":
        return <AiTab />;
      case "prompts":
        return <PromptsTab />;
      case "kb-templates":
        return <KBTemplatesTab novelId={novelId} />;
      case "learning":
        return <LearningTab novelId={novelId} />;
      case "background-tasks":
        return <BackgroundTasksPanel />;
      case "shortcuts":
        return <ShortcutsTab />;
      case "about":
        return <AboutTab />;
    }
  }

  return (
    <section className="flex-1 flex h-full" aria-labelledby="settings-view-title">
      <h1 id="settings-view-title" className="sr-only">
        {t("settings.title")}
      </h1>
      <SettingsSidebar activeCategory={activeCategory} onCategoryChange={handleCategoryChange} />
      <div className="flex-1 overflow-y-auto bg-background p-8">
        <div className="max-w-3xl">{renderContent()}</div>
      </div>
    </section>
  );
}
