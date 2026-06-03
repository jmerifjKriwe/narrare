"use client";

import { FileText } from "lucide-react";

interface SummaryCardProps {
  localLogline: string;
  localSynopsis: string;
  onLoglineChange: (value: string) => void;
  onSynopsisChange: (value: string) => void;
  t: (key: string) => string;
}

export function SummaryCard({
  localLogline,
  localSynopsis,
  onLoglineChange,
  onSynopsisChange,
  t,
}: SummaryCardProps) {
  return (
    <div className="bg-card border border-border rounded-lg p-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
          <FileText className="w-6 h-6" />
        </div>
        <div>
          <h3 className="font-medium">{t("settings.novelDetailsSection.summaryCard")}</h3>
          <p className="text-sm text-muted-foreground">
            {t("settings.novelDetailsSection.summaryCardDescription")}
          </p>
        </div>
      </div>
      <div className="ml-15 space-y-4">
        <div>
          <label htmlFor="novel-logline" className="text-sm font-medium mb-1 block">
            {t("settings.novelDetailsSection.loglineField")}
          </label>
          <p className="text-xs text-muted-foreground mb-2">
            {t("settings.novelDetailsSection.loglineFieldDescription")}
          </p>
          <input
            id="novel-logline"
            type="text"
            value={localLogline}
            onChange={(e) => onLoglineChange(e.target.value)}
            className="w-full max-w-md px-4 py-2 bg-background border border-border rounded-md text-sm"
          />
        </div>
        <div>
          <label htmlFor="novel-synopsis" className="text-sm font-medium mb-1 block">
            {t("settings.novelDetailsSection.synopsisField")}
          </label>
          <p className="text-xs text-muted-foreground mb-2">
            {t("settings.novelDetailsSection.synopsisFieldDescription")}
          </p>
          <textarea
            id="novel-synopsis"
            value={localSynopsis}
            onChange={(e) => onSynopsisChange(e.target.value)}
            rows={6}
            className="w-full max-w-lg px-4 py-2 bg-background border border-border rounded-md text-sm resize-y"
          />
        </div>
      </div>
    </div>
  );
}
