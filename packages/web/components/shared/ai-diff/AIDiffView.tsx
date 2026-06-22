"use client";

import { useTranslations } from "next-intl";
import type { AIDiffState, AIDiffViewModel } from "@/lib/ai-diff/contracts";
import { AIDiffBadge } from "./AIDiffBadge";
import { AIDiffSegmentList } from "./AIDiffSegmentList";

interface AIDiffViewProps {
  readonly viewModel: AIDiffViewModel;
  /** Author-control state. Caller-owned — the view never starts AI work. */
  readonly state: AIDiffState;
}

/**
 * Shared, accessible AI-diff surface (CR-AUFG-07-18).
 *
 * - `text` mode: inline diff via {@link AIDiffSegmentList} (Rewrite, Co-Author).
 * - `field` mode: whole-value before/after columns (KB Enhance) — no prose diff.
 *
 * The container is a `<section>` (semantic landmark; implicit `role="region"`
 * via its accessible name) carrying an sr summary of additions/removals so
 * screen readers announce change volume, not just per-segment labels.
 */
export function AIDiffView({ viewModel: vm, state }: AIDiffViewProps) {
  const t = useTranslations("studio");
  const added = vm.segments.filter((s) => s.kind === "added").length;
  const removed = vm.segments.filter((s) => s.kind === "removed").length;

  return (
    <section aria-label={t("aiDiff.srSummary", { added, removed })} className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {vm.label !== null && (
          <span className="text-xs font-medium text-muted-foreground">{vm.label}</span>
        )}
        <AIDiffBadge state={state} />
        {vm.provisional && (
          <span className="text-xs italic text-muted-foreground">{t("aiDiff.provisional")}</span>
        )}
      </div>

      {vm.mode === "text" ? (
        <div className="text-sm leading-relaxed">
          <AIDiffSegmentList segments={vm.segments} />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
          <div>
            <div className="mb-1 text-xs font-medium uppercase tracking-wider text-muted-foreground">
              {t("aiActions.original")}
            </div>
            <div className="whitespace-pre-wrap text-sm text-muted-foreground opacity-70 line-through">
              {vm.originalFull || <span className="italic not-italic">{t("kb.empty")}</span>}
            </div>
          </div>
          <div>
            <div className="mb-1 text-xs font-medium uppercase tracking-wider text-green-600 dark:text-green-400">
              {t("aiActions.suggested")}
            </div>
            <div className="whitespace-pre-wrap text-sm">{vm.suggestedFull}</div>
          </div>
        </div>
      )}
    </section>
  );
}
