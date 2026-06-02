"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  Brain,
  FileText,
  Info,
  Keyboard,
  Settings2,
  Sparkles,
  Target,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { AiTab } from "@/components/studio/settings/AiTab";
import { GeneralTab } from "@/components/studio/settings/GeneralTab";
import { KBTemplatesTab } from "@/components/studio/settings/KBTemplatesTab";
import { LearningTab } from "@/components/studio/settings/LearningTab";
import { NovelDetailsTab } from "@/components/studio/settings/NovelDetailsTab";
import { PromptsTab } from "@/components/studio/settings/PromptsTab";
import { WritingGoalsTab } from "@/components/studio/settings/WritingGoalsTab";
import { settingsApi } from "@/lib/api/client";

// --- Types ---

type SettingsCategory =
  | "novel-details"
  | "general"
  | "writing"
  | "ai"
  | "prompts"
  | "kb-templates"
  | "learning"
  | "shortcuts"
  | "about";

interface CategoryConfig {
  id: SettingsCategory;
  icon: typeof Settings2;
  labelKey: string;
}

interface SettingsViewProps {
  novelId: string;
}

// --- Static config ---

const CATEGORIES: CategoryConfig[] = [
  { id: "novel-details", icon: BookOpen, labelKey: "settings.novelDetails" },
  { id: "general", icon: Settings2, labelKey: "settings.general" },
  { id: "writing", icon: Target, labelKey: "settings.writingGoals" },
  { id: "ai", icon: Sparkles, labelKey: "settings.aiSetup" },
  { id: "prompts", icon: FileText, labelKey: "settings.promptsTab" },
  { id: "kb-templates", icon: BookOpen, labelKey: "settings.kbTemplates" },
  { id: "learning", icon: Brain, labelKey: "settings.learning" },
  { id: "shortcuts", icon: Keyboard, labelKey: "settings.shortcuts" },
  { id: "about", icon: Info, labelKey: "settings.about" },
];

const SHORTCUTS: Array<
  | { key: string; labelKey: string; descKey: string }
  | { keyKey: string; labelKey: string; descKey: string }
> = [
  {
    key: "Cmd+S",
    labelKey: "settings.shortcutsSection.save",
    descKey: "settings.shortcutsSection.saveDescription",
  },
  {
    key: "Cmd+N",
    labelKey: "settings.shortcutsSection.newChapter",
    descKey: "settings.shortcutsSection.newChapterDescription",
  },
  {
    key: "Cmd+K",
    labelKey: "settings.shortcutsSection.commandPalette",
    descKey: "settings.shortcutsSection.commandPaletteDescription",
  },
  {
    key: "Ctrl+B",
    labelKey: "settings.shortcutsSection.bold",
    descKey: "settings.shortcutsSection.boldDescription",
  },
  {
    key: "Ctrl+I",
    labelKey: "settings.shortcutsSection.italic",
    descKey: "settings.shortcutsSection.italicDescription",
  },
  {
    keyKey: "settings.shortcutsSection.selectText",
    labelKey: "settings.shortcutsSection.aiRewrite",
    descKey: "settings.shortcutsSection.aiRewriteDescription",
  },
  {
    key: "Tab",
    labelKey: "settings.shortcutsSection.ghostTextAccept",
    descKey: "settings.shortcutsSection.ghostTextAcceptDescription",
  },
  {
    key: "→",
    labelKey: "settings.shortcutsSection.ghostTextWord",
    descKey: "settings.shortcutsSection.ghostTextWordDescription",
  },
  {
    key: "Esc",
    labelKey: "settings.shortcutsSection.ghostTextDismiss",
    descKey: "settings.shortcutsSection.ghostTextDismissDescription",
  },
];

// --- Main Component ---

export function SettingsView({ novelId }: SettingsViewProps) {
  const t = useTranslations("studio");
  const queryClient = useQueryClient();
  const [activeCategory, setActiveCategory] = useState<SettingsCategory>("novel-details");

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

  // --- Category Sidebar ---
  const sidebar = (
    <div className="w-56 border-r border-border bg-card flex flex-col">
      <div className="p-4 border-b border-border">
        <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
          {t("settings.title")}
        </h2>
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        <div className="space-y-0.5">
          {CATEGORIES.map((cat) => {
            const Icon = cat.icon;
            const isActive = activeCategory === cat.id;
            return (
              <button
                type="button"
                key={cat.id}
                data-testid={`settings-tab-${cat.id}`}
                onClick={() => setActiveCategory(cat.id)}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-md transition-all text-sm ${
                  isActive
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "hover:bg-accent text-foreground"
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{t(cat.labelKey)}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );

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
      case "shortcuts":
        return renderShortcuts();
      case "about":
        return renderAbout();
    }
  }

  function renderShortcuts() {
    return (
      <div>
        <div className="mb-6">
          <h2 className="text-xl font-medium mb-1">{t("settings.shortcutsSection.title")}</h2>
          <p className="text-sm text-muted-foreground">
            {t("settings.shortcutsSection.description")}
          </p>
        </div>
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="space-y-0">
            {SHORTCUTS.map((shortcut, index) => (
              <div key={shortcut.labelKey}>
                <div className="flex items-center justify-between py-3">
                  <div>
                    <div className="text-sm font-medium">{t(shortcut.labelKey)}</div>
                    <div className="text-xs text-muted-foreground">{t(shortcut.descKey)}</div>
                  </div>
                  <kbd className="px-3 py-1.5 bg-muted rounded text-sm border border-border font-mono">
                    {"key" in shortcut ? shortcut.key : t(shortcut.keyKey)}
                  </kbd>
                </div>
                {index < SHORTCUTS.length - 1 && <div className="h-px bg-border" />}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  function renderAbout() {
    return (
      <div>
        <div className="mb-6">
          <h2 className="text-xl font-medium mb-1">{t("settings.aboutSection.title")}</h2>
          <p className="text-sm text-muted-foreground">{t("settings.aboutSection.description")}</p>
        </div>
        <div className="space-y-4">
          {/* App info card */}
          <div className="bg-card border border-border rounded-lg p-6">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-12 h-12 rounded-lg bg-primary flex items-center justify-center">
                <BookOpen className="w-6 h-6 text-primary-foreground" />
              </div>
              <div>
                <h3 className="text-lg font-medium">Narrare</h3>
                <p className="text-sm text-muted-foreground">
                  {t("settings.aboutSection.descriptionText")}
                </p>
              </div>
            </div>
            <div className="space-y-2 pt-4 border-t border-border">
              {[
                {
                  label: t("settings.aboutSection.version"),
                  value: "0.1.0",
                },
                {
                  label: t("settings.aboutSection.license"),
                  value: "MIT",
                },
                { label: t("settings.aboutSection.build"), value: "2026.05" },
              ].map((row) => (
                <div key={row.label} className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">{row.label}</span>
                  <span className="font-medium">{row.value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Features list */}
          <div className="bg-card border border-border rounded-lg p-6">
            <h3 className="font-medium mb-4">{t("settings.aboutSection.features")}</h3>
            <ul className="space-y-2">
              {[
                "settings.aboutSection.feature1",
                "settings.aboutSection.feature2",
                "settings.aboutSection.feature3",
                "settings.aboutSection.feature4",
                "settings.aboutSection.feature5",
              ].map((key) => (
                <li key={key} className="flex items-start gap-2 text-sm text-muted-foreground">
                  <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-muted-foreground flex-shrink-0" />
                  <span>{t(key)}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex h-full">
      {sidebar}
      <div className="flex-1 overflow-y-auto bg-background p-8">
        <div className="max-w-3xl">{renderContent()}</div>
      </div>
    </div>
  );
}
