import { useEffect } from "react";
import type { SimulatedRow } from "@/lib/importing/simulateOperations";
import type { ImportOpsState, ImportPreviewResponse, ImportSelection } from "@/types";

/**
 * Legacy (v1) projection of the stable-key edit state. ImportModal and the
 * wizard completion still commit through the v1 members until T7 migrates
 * them to buildAdjustments. The projection is EXACT while no ops are set
 * (final == original space); with ops, only what v1 space can represent is
 * projected — originals whose every part is excluded (never a partial drop:
 * that would silently delete content) and head-part renames. Part-level
 * edits live on in excludedKeys/titleByKey for buildAdjustments.
 */
function legacyProjection(
  rows: readonly SimulatedRow[],
  excludedKeys: ReadonlySet<string>,
  titleByKey: Readonly<Record<string, string>>,
): Pick<ImportSelection, "excludedIndices" | "titleOverrides"> {
  const partCount = new Map<number, number>();
  const excludedCount = new Map<number, number>();
  for (const row of rows) {
    partCount.set(row.origIndex, (partCount.get(row.origIndex) ?? 0) + 1);
    if (excludedKeys.has(row.key)) {
      excludedCount.set(row.origIndex, (excludedCount.get(row.origIndex) ?? 0) + 1);
    }
  }
  const excludedIndices = [...partCount]
    .filter(([origIndex, count]) => excludedCount.get(origIndex) === count)
    .map(([origIndex]) => origIndex)
    .sort((a, b) => a - b);
  const titleOverrides: Record<string, string> = {};
  for (const row of rows) {
    const title = titleByKey[row.key];
    if (row.part === 0 && title !== undefined) titleOverrides[String(row.origIndex)] = title;
  }
  return { excludedIndices, titleOverrides };
}

interface SelectionPublishParams {
  /** Mutable to mirror ImportSelection.files (published verbatim). */
  readonly files: File[];
  readonly preview: ImportPreviewResponse | null;
  readonly ops: ImportOpsState;
  readonly opsEnabled: boolean;
  readonly excludedKeys: ReadonlySet<string>;
  readonly titleByKey: Readonly<Record<string, string>>;
  readonly rows: readonly SimulatedRow[];
  readonly onSelectionChange: (selection: ImportSelection | null) => void;
}

/**
 * Publishes the selection upward; the panel performs NO commit itself — the
 * modal commits for existing novels, the wizard commits at Step-5 completion
 * (T7 migrates both to buildAdjustments). The server re-validates everything
 * at commit.
 *
 * Selection lifecycle: a provisional v1-shaped selection is published at
 * pick time and refined once the preview resolves; a preview failure
 * retracts it (null), so nothing can be committed off an unanalyzed
 * preview. The commit endpoint re-parses and re-validates the raw files
 * server-side, so the provisional window is safe.
 */
export function useSelectionPublish({
  files,
  preview,
  ops,
  opsEnabled,
  excludedKeys,
  titleByKey,
  rows,
  onSelectionChange,
}: SelectionPublishParams): void {
  useEffect(() => {
    if (files.length === 0) {
      onSelectionChange(null);
      return;
    }
    if (!preview) {
      // Provisional pick-time publish (v1 parity): server re-parses at commit.
      onSelectionChange({
        files,
        excludedIndices: [],
        titleOverrides: {},
        includedCount: files.length,
      });
      return;
    }
    const included = rows.filter((row) => !excludedKeys.has(row.key)).length;
    const legacy = legacyProjection(rows, excludedKeys, titleByKey);
    onSelectionChange(
      opsEnabled
        ? {
            files,
            ...legacy,
            items: preview.items,
            ops,
            excludedKeys: [...excludedKeys],
            titleByKey,
            includedCount: included,
          }
        : // v1 server: publish the pure v1 shape (no ops UI exists to produce
          // v2 state — and v1-shaped consumers assert exactly this shape).
          { files, ...legacy, includedCount: included },
    );
  }, [files, preview, opsEnabled, ops, excludedKeys, titleByKey, rows, onSelectionChange]);
}
