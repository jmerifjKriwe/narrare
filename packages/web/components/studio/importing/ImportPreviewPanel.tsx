"use client";

import { useTranslations } from "next-intl";
import { useMemo, useRef, useState } from "react";
import { importApi } from "@/lib/api/client";
import { applySplit, clearSplit, mergeWithNext, unmergeAt } from "@/lib/importing/opsState";
import {
  EMPTY_OPS,
  serverSupportsOps,
  simulateOperations,
} from "@/lib/importing/simulateOperations";
import type { ImportOpsState, ImportPreviewResponse, ImportSelection } from "@/types";
import { PreviewRow } from "./PreviewRow";
import { useSelectionPublish } from "./useSelectionPublish";

/**
 * Shared import surface (F1): pick files → server preview → split/merge
 * boundary editing (original-space ops) + include/exclude/rename on the
 * simulated FINAL list (stable row keys `{origIndex}#{part}` — edits never
 * key on final indices). Selection publishing lives in useSelectionPublish;
 * each simulated row renders via PreviewRow.
 */
interface ImportPreviewPanelProps {
  readonly onSelectionChange: (selection: ImportSelection | null) => void;
}

export function ImportPreviewPanel({ onSelectionChange }: ImportPreviewPanelProps) {
  const t = useTranslations("importing");
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [ops, setOps] = useState<ImportOpsState>(EMPTY_OPS);
  const [excludedKeys, setExcludedKeys] = useState<Set<string>>(new Set());
  const [titleByKey, setTitleByKey] = useState<Record<string, string>>({});
  const [pickerFor, setPickerFor] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Capability probe (spec §7): v1 servers omit split_candidates — the whole
  // ops UI stays gated off (plain v1 panel, no dead buttons, pure v1 publish).
  const opsEnabled = preview !== null && serverSupportsOps(preview);
  const rows = useMemo(
    () => (preview ? simulateOperations(preview.items, ops) : []),
    [preview, ops],
  );
  // First row per original index (undo-split anchor).
  const firstKeyPerOrig = useMemo(() => {
    const map = new Map<number, string>();
    for (const row of rows) if (!map.has(row.origIndex)) map.set(row.origIndex, row.key);
    return map;
  }, [rows]);

  useSelectionPublish({
    files,
    preview,
    ops,
    opsEnabled,
    excludedKeys,
    titleByKey,
    rows,
    onSelectionChange,
  });

  const handleFiles = async (picked: FileList | null) => {
    if (!picked || picked.length === 0) return;
    // Deterministic order BEFORE upload — the server never re-orders (spec §5.1)
    const sorted = [...picked].sort((a, b) =>
      a.name.localeCompare(b.name, undefined, { numeric: true }),
    );
    setFiles(sorted);
    setOps(EMPTY_OPS);
    setExcludedKeys(new Set());
    setTitleByKey({});
    setPickerFor(null);
    setError(null);
    setPreview(null);
    setIsLoading(true);
    try {
      const result = await importApi.preview(sorted);
      if (!result) return;
      setPreview(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      onSelectionChange(null);
    } finally {
      setIsLoading(false);
    }
  };

  const toggleRow = (key: string) => {
    setExcludedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const renameRow = (key: string, suggested: string, value: string) => {
    setTitleByKey((prev) => {
      const next = { ...prev };
      // Empty input reverts to the suggested title (never store empties).
      if (value.trim() === "" || value === suggested) delete next[key];
      else next[key] = value;
      return next;
    });
  };

  return (
    <div className="flex flex-col gap-3" data-testid="import-preview-panel">
      <input
        ref={inputRef}
        id="import-file-input"
        type="file"
        multiple
        accept=".md,.txt"
        aria-label={t("chooseFiles")}
        className="block w-full text-sm text-muted-foreground file:mr-3 file:rounded-md file:border-0 file:bg-primary file:px-3 file:py-1.5 file:text-sm file:text-primary-foreground"
        onChange={(e) => void handleFiles(e.target.files)}
      />

      {isLoading && <p className="text-sm text-muted-foreground animate-pulse">{t("loading")}</p>}
      {error && (
        <p className="bg-destructive/10 text-destructive rounded-lg p-3 text-sm" role="alert">
          {t("errors.previewFailed", { message: error })}
        </p>
      )}

      {preview && (
        <>
          <p className="text-xs text-muted-foreground">
            {t("summary", {
              files: preview.file_count,
              chapters: rows.length,
              words: rows.reduce((sum, row) => sum + row.wordCount, 0).toLocaleString(),
            })}
          </p>
          <ul className="max-h-72 overflow-y-auto rounded-md border border-border">
            {rows.map((row) => (
              <PreviewRow
                key={row.key}
                row={row}
                ops={ops}
                items={preview.items}
                candidates={preview.items[row.origIndex]?.split_candidates ?? []}
                opsEnabled={opsEnabled}
                included={!excludedKeys.has(row.key)}
                currentTitle={titleByKey[row.key] ?? row.title}
                isHead={firstKeyPerOrig.get(row.origIndex) === row.key}
                pickerOpen={pickerFor === row.origIndex}
                onToggle={() => toggleRow(row.key)}
                onRename={(value) => renameRow(row.key, row.title, value)}
                onSplitOpen={() => setPickerFor(row.origIndex)}
                onSplitUndo={() => setOps((o) => clearSplit(o, row.origIndex))}
                onMerge={() => setOps((o) => mergeWithNext(o, row.origIndex, preview.items))}
                onUnmerge={() => setOps((o) => unmergeAt(o, row.origIndex))}
                onPickerApply={(ordinals) => {
                  setOps((o) => applySplit(o, row.origIndex, ordinals));
                  setPickerFor(null);
                }}
                onPickerCancel={() => setPickerFor(null)}
              />
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
