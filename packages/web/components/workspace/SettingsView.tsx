"use client";

import { Moon, Sun, Target, Sparkles, Settings2, Keyboard, Info, BookOpen } from "lucide-react";
import { useState } from "react";
import { useTranslations } from "next-intl";
import { GeneralSettings } from "./settings/GeneralSettings";
import { WritingSettings } from "./settings/WritingSettings";
import { AiSettings } from "./settings/AiSettings";
import { ShortcutsSettings } from "./settings/ShortcutsSettings";
import { AboutSettings } from "./settings/AboutSettings";

export type SettingsCategory = "general" | "writing" | "ai" | "shortcuts" | "about";

interface CategoryDef {
  id: SettingsCategory;
  labelKey: string;
  icon: React.ComponentType<{ className?: string }>;
}

const CATEGORIES: CategoryDef[] = [
  { id: "general", labelKey: "general", icon: Settings2 },
  { id: "writing", labelKey: "writing", icon: Target },
  { id: "ai", labelKey: "ai", icon: Sparkles },
  { id: "shortcuts", labelKey: "shortcuts", icon: Keyboard },
  { id: "about", labelKey: "about", icon: Info },
];

export function SettingsView() {
  const t = useTranslations("settings");
  const [activeCategory, setActiveCategory] = useState<SettingsCategory>("general");

  return (
    <div className="flex-1 flex h-full">
      {/* Sub-sidebar */}
      <div className="w-56 border-r border-border bg-card flex flex-col">
        <div className="p-4 border-b border-border">
          <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
            {t("title")}
          </h3>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          <div className="space-y-0.5">
            {CATEGORIES.map((category) => {
              const Icon = category.icon;
              const isActive = activeCategory === category.id;
              return (
                <button
                  key={category.id}
                  type="button"
                  onClick={() => setActiveCategory(category.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-md transition-all text-sm ${
                    isActive
                      ? "bg-primary text-primary-foreground shadow-sm"
                      : "hover:bg-accent text-foreground"
                  }`}
                  aria-current={isActive ? "true" : undefined}
                >
                  <Icon className="w-4 h-4" />
                  <span>{t(category.labelKey)}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-y-auto bg-background p-8">
        <div className="max-w-3xl">
          {activeCategory === "general" && <GeneralSettings />}
          {activeCategory === "writing" && <WritingSettings />}
          {activeCategory === "ai" && <AiSettings />}
          {activeCategory === "shortcuts" && <ShortcutsSettings />}
          {activeCategory === "about" && <AboutSettings />}
        </div>
      </div>
    </div>
  );
}
