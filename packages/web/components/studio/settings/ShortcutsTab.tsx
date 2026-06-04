import { useTranslations } from "next-intl";
import { SETTINGS_SHORTCUTS } from "./settings-view-config";

export function ShortcutsTab() {
  const t = useTranslations("studio");

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
          {SETTINGS_SHORTCUTS.map((shortcut, index) => (
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
              {index < SETTINGS_SHORTCUTS.length - 1 && <div className="h-px bg-border" />}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
