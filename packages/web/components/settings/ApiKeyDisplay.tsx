"use client";

import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/Button";

interface ApiKeyDisplayProps {
  readonly last4: string;
  readonly hasKey: boolean;
  readonly onChange: () => void;
}

export function ApiKeyDisplay({ last4, hasKey, onChange }: ApiKeyDisplayProps) {
  const t = useTranslations("settings-ai.apiKeyDisplay");

  if (!hasKey) {
    return <span className="text-[0.8125rem] text-muted-foreground">{t("noKey")}</span>;
  }

  return (
    <div className="flex items-center gap-3">
       <span className="font-mono text-[0.875rem] text-muted-foreground tracking-wider select-none">
        {"••••••••"}
        {last4}
      </span>
      <Button type="button" variant="ghost" size="sm" onClick={onChange}>
        {t("change")}
      </Button>
    </div>
  );
}
