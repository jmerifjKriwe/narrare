"use client";

import { Check } from "lucide-react";
import { useTranslations } from "next-intl";

import { btnSecondary } from "./coauthor-styles";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface CoAuthorDonePhaseProps {
  readonly onClose: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CoAuthorDonePhase({ onClose }: CoAuthorDonePhaseProps) {
  const t = useTranslations("studio");

  return (
    <div className="flex flex-col items-center justify-center py-8 space-y-4">
      <div className="w-12 h-12 rounded-full bg-green-500/10 flex items-center justify-center">
        <Check className="w-6 h-6 text-green-500" />
      </div>
      <p className="text-sm font-medium">{t("coAuthor.done")}</p>
      <button type="button" onClick={onClose} className={btnSecondary}>
        {t("coAuthor.close")}
      </button>
    </div>
  );
}
