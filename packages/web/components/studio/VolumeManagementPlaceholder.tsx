"use client";

import { Library } from "lucide-react";
import { useTranslations } from "next-intl";

export function VolumeManagementPlaceholder() {
  const t = useTranslations("studio.volumes");

  return (
    <div className="flex-1 flex items-center justify-center h-full text-muted-foreground">
      <div className="text-center">
        <Library className="w-16 h-16 mx-auto mb-4 opacity-10" />
        <p className="text-lg mb-1">{t("comingSoon")}</p>
        <p className="text-sm">{t("comingSoonDesc")}</p>
      </div>
    </div>
  );
}
