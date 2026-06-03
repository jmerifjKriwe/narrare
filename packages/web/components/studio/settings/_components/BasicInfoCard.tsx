"use client";

import { BookOpen } from "lucide-react";

interface BasicInfoCardProps {
  localTitle: string;
  localAuthor: string;
  localWritingLanguage: string;
  onTitleChange: (value: string) => void;
  onAuthorChange: (value: string) => void;
  onWritingLanguageChange: (value: string) => void;
  t: (key: string) => string;
}

export function BasicInfoCard({
  localTitle,
  localAuthor,
  localWritingLanguage,
  onTitleChange,
  onAuthorChange,
  onWritingLanguageChange,
  t,
}: BasicInfoCardProps) {
  return (
    <div className="bg-card border border-border rounded-lg p-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
          <BookOpen className="w-6 h-6" />
        </div>
        <div>
          <h3 className="font-medium">{t("settings.novelDetailsSection.basicInfo")}</h3>
          <p className="text-sm text-muted-foreground">
            {t("settings.novelDetailsSection.basicInfoDescription")}
          </p>
        </div>
      </div>
      <div className="ml-15 space-y-4">
        <div>
          <label htmlFor="novel-title" className="text-sm font-medium mb-1 block">
            {t("settings.novelDetailsSection.titleField")}
          </label>
          <p className="text-xs text-muted-foreground mb-2">
            {t("settings.novelDetailsSection.titleFieldDescription")}
          </p>
          <input
            id="novel-title"
            type="text"
            value={localTitle}
            onChange={(e) => onTitleChange(e.target.value)}
            className="w-full max-w-md px-4 py-2 bg-background border border-border rounded-md text-sm"
          />
        </div>
        <div>
          <label htmlFor="novel-author" className="text-sm font-medium mb-1 block">
            {t("settings.novelDetailsSection.authorField")}
          </label>
          <p className="text-xs text-muted-foreground mb-2">
            {t("settings.novelDetailsSection.authorFieldDescription")}
          </p>
          <input
            id="novel-author"
            type="text"
            value={localAuthor}
            onChange={(e) => onAuthorChange(e.target.value)}
            className="w-full max-w-md px-4 py-2 bg-background border border-border rounded-md text-sm"
          />
        </div>
        <div>
          <label htmlFor="novel-language" className="text-sm font-medium mb-1 block">
            {t("settings.novelDetailsSection.languageField")}
          </label>
          <p className="text-xs text-muted-foreground mb-2">
            {t("settings.novelDetailsSection.languageFieldDescription")}
          </p>
          <input
            id="novel-language"
            type="text"
            value={localWritingLanguage}
            onChange={(e) => onWritingLanguageChange(e.target.value)}
            maxLength={100}
            className="w-full max-w-md px-4 py-2 bg-background border border-border rounded-md text-sm"
          />
        </div>
      </div>
    </div>
  );
}
