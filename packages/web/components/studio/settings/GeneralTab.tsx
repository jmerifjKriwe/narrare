"use client";

import { Loader2, MessageSquare } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { ThemeSection } from "./ThemeSection";

interface GeneralTabProps {
  displayName: string;
  uiLanguage: string;
  isLoading: boolean;
  onSaveProfile: (payload: { display_name?: string; ui_language?: string }) => void;
}

export function GeneralTab({ displayName, uiLanguage, isLoading, onSaveProfile }: GeneralTabProps) {
  const t = useTranslations("studio");
  const router = useRouter();

  const [localDisplayName, setLocalDisplayName] = useState(displayName);
  const [localLanguage, setLocalLanguage] = useState(uiLanguage);
  const [dirty, setDirty] = useState(false);

  // Sync props to local state when query resolves / component remounts
  useEffect(() => {
    setLocalDisplayName(displayName);
  }, [displayName]);

  useEffect(() => {
    setLocalLanguage(uiLanguage);
  }, [uiLanguage]);

  function handleDisplayNameChange(value: string) {
    setLocalDisplayName(value);
    setDirty(true);
  }

  function handleLanguageChange(value: string) {
    setLocalLanguage(value);
    setDirty(true);
  }

  function handleSave() {
    onSaveProfile({ display_name: localDisplayName, ui_language: localLanguage });

    // Set locale cookie so next-intl's getLocale() picks up the new language
    // biome-ignore lint/suspicious/noDocumentCookie: synchronous cookie needed before router.refresh()
    document.cookie = `NEXT_LOCALE=${localLanguage};path=/;max-age=${60 * 60 * 24 * 365};sameSite=lax`;

    // Trigger server re-render with the new locale
    router.refresh();
    setDirty(false);
  }

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
        <h2 className="text-xl font-medium mb-1">{t("settings.generalSection.title")}</h2>
        <p className="text-sm text-muted-foreground">{t("settings.generalSection.description")}</p>
      </div>
      <div className="space-y-4">
        {/* Theme settings (color mode + theme selector) */}
        <ThemeSection />

        {/* Display name */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
              <MessageSquare className="w-6 h-6" />
            </div>
            <div>
              <h3 className="font-medium">{t("settings.generalSection.displayName")}</h3>
              <p className="text-sm text-muted-foreground">
                {t("settings.generalSection.displayNameDescription")}
              </p>
            </div>
          </div>
          <div className="ml-15">
            <input
              type="text"
              value={localDisplayName}
              onChange={(e) => handleDisplayNameChange(e.target.value)}
              className="w-full max-w-md px-4 py-2 bg-background border border-border rounded-md text-sm"
            />
          </div>
        </div>

        {/* Language */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
                <MessageSquare className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-medium">{t("settings.generalSection.language")}</h3>
                <p className="text-sm text-muted-foreground">
                  {t("settings.generalSection.languageDescription")}
                </p>
              </div>
            </div>
            <select
              value={localLanguage}
              onChange={(e) => handleLanguageChange(e.target.value)}
              className="px-4 py-2 bg-background border border-border rounded-md text-sm"
            >
              <option value="de">{t("settings.generalSection.langDe")}</option>
              <option value="en">{t("settings.generalSection.langEn")}</option>
              <option value="fr">{t("settings.generalSection.langFr")}</option>
            </select>
          </div>
        </div>

        {/* Save button */}
        {dirty && (
          <div className="flex justify-end">
            <button
              type="button"
              onClick={handleSave}
              className="px-6 py-2.5 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity shadow-sm text-sm"
            >
              {t("settings.ai.save")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
