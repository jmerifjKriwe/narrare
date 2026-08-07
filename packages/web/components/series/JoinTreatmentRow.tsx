"use client";

/**
 * JoinTreatmentRow — a single per-entry treatment in a JoinPreview
 * (Spec 1, Slice 4, Task 4.8).
 *
 * Extracted from JoinPreviewDialog (RULE-04: one responsibility per file). Each
 * row shows the entry slug, its entity type, the arrow to its resolved scope
 * (Series-Canon vs Novel-Overlay) and the reason. All copy goes through
 * `useTranslations("studio")` under `series.join.*` (keys added by Task 4.9).
 *
 * C3 fix: the reason is resolved from the machine-stable `reason_code`
 * (``series.join.reason.<code>``), NOT the free-text English ``reason`` tooltip
 * — the latter is unresolvable as an i18n key and silently broke the preview.
 * The entity-type label reuses the shared ``kb.<type>s`` keys (the canonical
 * labels for all 8 KB entity types) rather than a parallel
 * ``series.join.entity.*`` namespace.
 */
import { ArrowRight } from "lucide-react";
import { useTranslations } from "next-intl";
import type { JoinEntryTreatment } from "@/types";

interface JoinTreatmentRowProps {
  readonly treatment: JoinEntryTreatment;
}

export function JoinTreatmentRow({ treatment }: JoinTreatmentRowProps) {
  const t = useTranslations("studio");
  const targetLabel =
    treatment.target_scope === "series"
      ? t("series.join.targetSeries")
      : t("series.join.targetNovel");
  // C3: resolve the reason from the stable code, not the free-text tooltip.
  const reasonLabel = t(`series.join.reason.${treatment.reason_code}`);
  // Reuse the shared KB entity-type labels (kb.characters, kb.systems, …).
  const entityLabel = t(`kb.${treatment.entity_type}s`);

  return (
    <li
      data-testid="join-treatment"
      className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 text-sm"
    >
      <span className="font-medium text-foreground">{treatment.slug}</span>
      <span className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
        {entityLabel}
      </span>
      <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
      <span className="text-foreground">{targetLabel}</span>
      <span className="text-muted-foreground">{reasonLabel}</span>
    </li>
  );
}
