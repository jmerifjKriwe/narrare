"use client";

/**
 * BulkStateChip — per-chapter job state chip shared by the bulk progress list
 * and the review chapter rail (F2 T7). Owns the state → label-key and
 * state → color mappings so both views stay in sync.
 *
 * @module BulkStateChip
 */

import { useTranslations } from "next-intl";
import type { BulkChapterState } from "@/lib/api/bulkExtraction";

const STATE_LABEL_KEYS: Record<BulkChapterState, string> = {
  pending: "kb.bulkExtraction.statePending",
  running: "kb.bulkExtraction.stateRunning",
  done: "kb.bulkExtraction.stateDone",
  failed: "kb.bulkExtraction.stateFailed",
};

const STATE_CHIP_CLASSES: Record<BulkChapterState, string> = {
  pending: "bg-muted text-muted-foreground",
  running: "bg-primary/10 text-primary",
  done: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
  failed: "bg-destructive/10 text-destructive",
};

export function BulkStateChip({ state }: { readonly state: BulkChapterState }) {
  const t = useTranslations("studio");
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full ${STATE_CHIP_CLASSES[state]}`}>
      {t(STATE_LABEL_KEYS[state])}
    </span>
  );
}
