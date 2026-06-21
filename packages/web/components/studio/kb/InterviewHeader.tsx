"use client";

/**
 * InterviewHeader — Header bar for the KB Interview view.
 *
 * Extracted from KBInterviewView for RULE-04 compliance.
 */

import { ArrowLeft, MessageSquare } from "lucide-react";
import { useTranslations } from "next-intl";

interface InterviewHeaderProps {
  questionCount: number;
  onBack: () => void;
}

export function InterviewHeader({ questionCount, onBack }: InterviewHeaderProps) {
  const t = useTranslations("studio");

  return (
    <div className="flex items-center justify-between p-4 border-b border-border bg-card">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onBack}
          className="p-1.5 text-muted-foreground hover:text-foreground rounded-md hover:bg-muted transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex items-center gap-2">
          <MessageSquare className="w-5 h-5 text-purple-500" />
          <h3 className="font-medium">{t("kb.interviewMode")}</h3>
        </div>
      </div>
      <div className="text-sm text-muted-foreground">
        {t("kb.interviewProgress", { current: questionCount })}
      </div>
    </div>
  );
}
