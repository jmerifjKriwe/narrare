"use client";
import { useTranslations } from "next-intl";
import { Switch } from "@/components/ui/switch";

export function AdaptiveToggle({
  enabled,
  onToggle,
  pending,
}: {
  enabled: boolean;
  onToggle: (next: boolean) => void;
  pending: boolean;
}) {
  const t = useTranslations("adaptive");
  return (
    <div className="flex items-center justify-between gap-4">
      <div>
        <p className="font-medium">{t("enableLabel")}</p>
        <p className="text-sm text-muted-foreground">{t("enableDescription")}</p>
      </div>
      <Switch
        checked={enabled}
        onCheckedChange={onToggle}
        disabled={pending}
        aria-label={t("enableLabel")}
      />
    </div>
  );
}
