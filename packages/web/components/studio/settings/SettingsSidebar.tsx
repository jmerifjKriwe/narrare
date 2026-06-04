import { useTranslations } from "next-intl";
import { SETTINGS_CATEGORIES, type SettingsCategory } from "./settings-view-config";

interface SettingsSidebarProps {
  activeCategory: SettingsCategory;
  onCategoryChange: (category: SettingsCategory) => void;
}

export function SettingsSidebar({ activeCategory, onCategoryChange }: SettingsSidebarProps) {
  const t = useTranslations("studio");

  return (
    <div className="w-56 border-r border-border bg-card flex flex-col">
      <div className="p-4 border-b border-border">
        <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
          {t("settings.title")}
        </h2>
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        <div className="space-y-0.5">
          {SETTINGS_CATEGORIES.map((category) => {
            const Icon = category.icon;
            const isActive = activeCategory === category.id;

            return (
              <button
                type="button"
                key={category.id}
                data-testid={`settings-tab-${category.id}`}
                onClick={() => onCategoryChange(category.id)}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-md transition-all text-sm ${
                  isActive
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "hover:bg-accent text-foreground"
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{t(category.labelKey)}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
