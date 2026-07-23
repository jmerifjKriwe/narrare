"use client";
import { useTranslations } from "next-intl";
import type { AdaptiveSourceSummary } from "@/types";

export function AdaptiveSourceList({
  sources,
  hasAnySignal,
}: {
  sources: AdaptiveSourceSummary;
  hasAnySignal: boolean;
}) {
  const t = useTranslations("adaptive");
  const rows = [
    { labelKey: "source.preference", text: sources.preference_text },
    { labelKey: "source.voice_profiles", text: sources.voice_profiles_text },
    { labelKey: "source.style_constraints", text: sources.style_constraints_text },
    { labelKey: "source.avoidance_patterns", text: sources.avoidance_patterns_text },
  ];
  if (!hasAnySignal) {
    return <p className="text-sm text-muted-foreground">{t("noSignals")}</p>;
  }
  return (
    <div className="space-y-3">
      <p className="font-medium">{t("sourcesTitle")}</p>
      <dl className="space-y-2">
        {rows.map(({ labelKey, text }) => (
          <div key={labelKey}>
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">{t(labelKey)}</dt>
            <dd className="text-sm">{text || t("source.empty")}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
