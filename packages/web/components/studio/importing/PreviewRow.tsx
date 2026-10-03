"use client";

import { useTranslations } from "next-intl";
import { canMergeWithNext } from "@/lib/importing/opsState";
import type { SimulatedRow } from "@/lib/importing/simulateOperations";
import type { ImportOpsState, ImportPreviewResponse, ImportSplitCandidate } from "@/types";
import { SplitCandidatePicker } from "./SplitCandidatePicker";

/**
 * Honest merge affordance (T5b review rider): mergeWithNext grows the run
 * CONTAINING the clicked chapter — a click on the chapter directly AFTER a
 * run is absorbed INTO that run, i.e. from the clicked row's perspective the
 * merge goes backward. The label names the direction the user actually gets.
 */
function mergeGrowsBackward(ops: ImportOpsState, index: number): boolean {
  return (
    !ops.merges.some((run) => run.includes(index)) &&
    ops.merges.some((run) => run.includes(index - 1))
  );
}

interface PreviewRowProps {
  readonly row: SimulatedRow;
  /** Current ops state — split/merge affordances are row-local projections. */
  readonly ops: ImportOpsState;
  /** Original-space preview items (merge feasibility lives on them). */
  readonly items: ImportPreviewResponse["items"];
  /** Split candidates of this row's original chapter (capped server-side). */
  readonly candidates: readonly ImportSplitCandidate[];
  readonly opsEnabled: boolean;
  readonly included: boolean;
  readonly currentTitle: string;
  /** First FINAL row of the original chapter — the undo-split anchor. */
  readonly isHead: boolean;
  readonly pickerOpen: boolean;
  readonly onToggle: () => void;
  readonly onRename: (value: string) => void;
  readonly onSplitOpen: () => void;
  readonly onSplitUndo: () => void;
  readonly onMerge: () => void;
  readonly onUnmerge: () => void;
  readonly onPickerApply: (ordinals: number[]) => void;
  readonly onPickerCancel: () => void;
}

/**
 * One simulated FINAL row (stable key `{origIndex}#{part}`): include/rename
 * editing, split/merge badges, the ops buttons and the inline split candidate
 * picker. Pure projection of its props — all state transitions stay owned by
 * the panel via callbacks.
 */
export function PreviewRow({
  row,
  ops,
  items,
  candidates,
  opsEnabled,
  included,
  currentTitle,
  isHead,
  pickerOpen,
  onToggle,
  onRename,
  onSplitOpen,
  onSplitUndo,
  onMerge,
  onUnmerge,
  onPickerApply,
  onPickerCancel,
}: PreviewRowProps) {
  const t = useTranslations("importing");
  const tOps = useTranslations("importing.ops");
  const isSplit = ops.splits[row.origIndex] !== undefined;
  const isSplitHead = isSplit && isHead;
  const splittable =
    opsEnabled && row.part === 0 && !row.isMerged && !isSplit && candidates.length > 0;
  const mergeable = opsEnabled && canMergeWithNext(items, ops, row.origIndex);

  return (
    <li
      className="flex flex-col border-b border-border/50 px-3 py-2 last:border-b-0"
      data-testid={`import-row-${row.key}`}
    >
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={included}
          onChange={onToggle}
          aria-label={t("column.include")}
          className="h-4 w-4"
        />
        {/* Real <label> (not aria-label) so each title field is
            named after ITS chapter for screen readers. */}
        <label htmlFor={`import-chapter-title-${row.key}`} className="sr-only">
          {currentTitle}
        </label>
        <input
          id={`import-chapter-title-${row.key}`}
          type="text"
          value={currentTitle}
          onChange={(e) => onRename(e.target.value)}
          className="min-w-0 flex-1 rounded border border-border bg-background px-2 py-1 text-sm"
        />
        <span className="shrink-0 text-xs text-muted-foreground">
          {t("column.words")}: {row.wordCount.toLocaleString()}
        </span>
        {row.isMerged && (
          <span className="shrink-0 rounded bg-accent px-1.5 py-0.5 text-[10px] text-accent-foreground">
            {tOps("mergedBadge", { count: row.mergedCount })}
          </span>
        )}
        {isSplit && !row.isMerged && (
          <span className="shrink-0 rounded bg-accent px-1.5 py-0.5 text-[10px] text-accent-foreground">
            {tOps("partBadge", { part: row.part + 1 })}
          </span>
        )}
        <span
          className="shrink-0 max-w-32 truncate text-xs text-muted-foreground/70"
          title={row.sourceFile}
        >
          {row.sourceFile}
        </span>
      </div>
      {opsEnabled && (
        <div className="mt-1 flex flex-wrap gap-2 pl-6 text-xs">
          {splittable && (
            <button
              type="button"
              onClick={onSplitOpen}
              className="text-primary underline-offset-2 hover:underline"
            >
              {tOps("split")}
            </button>
          )}
          {isSplitHead && (
            <button
              type="button"
              onClick={onSplitUndo}
              className="text-primary underline-offset-2 hover:underline"
            >
              {tOps("undoSplit")}
            </button>
          )}
          {mergeable && (
            <button
              type="button"
              onClick={onMerge}
              className="text-primary underline-offset-2 hover:underline"
            >
              {mergeGrowsBackward(ops, row.origIndex)
                ? tOps("mergeWithPrevious")
                : tOps("mergeWithNext")}
            </button>
          )}
          {row.isMerged && (
            <button
              type="button"
              onClick={onUnmerge}
              className="text-primary underline-offset-2 hover:underline"
            >
              {tOps("undoMerge")}
            </button>
          )}
        </div>
      )}
      {pickerOpen && (
        <SplitCandidatePicker
          candidates={candidates}
          onApply={onPickerApply}
          onCancel={onPickerCancel}
        />
      )}
    </li>
  );
}
