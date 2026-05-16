"use client";

import { useTranslations } from "next-intl";

interface ShortcutDef {
  labelKey: string;
  descKey: string;
  keys: string;
}

const SHORTCUTS: ShortcutDef[] = [
  { labelKey: "save", descKey: "saveDescription", keys: "Ctrl + S" },
  { labelKey: "newChapter", descKey: "newChapterDescription", keys: "Ctrl + N" },
  { labelKey: "bold", descKey: "boldDescription", keys: "Ctrl + B" },
  { labelKey: "italic", descKey: "italicDescription", keys: "Ctrl + I" },
  { labelKey: "aiRephrase", descKey: "aiRephraseDescription", keys: "selectText" },
  { labelKey: "commandPalette", descKey: "commandPaletteDescription", keys: "Ctrl + K" },
  { labelKey: "focusMode", descKey: "focusModeDescription", keys: "Ctrl + Shift + F" },
  { labelKey: "sidebarToggle", descKey: "sidebarToggleDescription", keys: "Ctrl + \\" },
];

export function ShortcutsSettings() {
  const t = useTranslations("settings");

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-2xl mb-2">{t("shortcuts")}</h2>
        <p className="text-sm text-muted-foreground">
          {t("shortcutsDescription")}
        </p>
      </div>

      <div className="bg-card border border-border rounded-lg p-6">
        <div className="space-y-4">
          {SHORTCUTS.map((shortcut, index) => (
            <div key={shortcut.labelKey}>
              <div className="flex items-center justify-between py-2">
                <div>
                  <div className="font-medium mb-1">{t(shortcut.labelKey)}</div>
                  <div className="text-sm text-muted-foreground">
                    {t(shortcut.descKey)}
                  </div>
                </div>
                <kbd className="px-3 py-1.5 bg-muted rounded text-sm border border-border font-mono">
                  {/* Use i18n key only for "Markieren" entry, otherwise show raw shortcut */}
                  {shortcut.keys === "selectText" ? t("selectText") : shortcut.keys}
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
