import { useEffect } from "react";
import { EMPTY_OPS, type SimulatedRow } from "@/lib/importing/simulateOperations";
import type { ImportOpsState, ImportPreviewResponse, ImportSelection } from "@/types";

interface SelectionPublishParams {
  /** Mutable to mirror ImportSelection.files (published verbatim). */
  readonly files: File[];
  readonly preview: ImportPreviewResponse | null;
  readonly ops: ImportOpsState;
  readonly excludedKeys: ReadonlySet<string>;
  readonly titleByKey: Readonly<Record<string, string>>;
  readonly rows: readonly SimulatedRow[];
  /**
   * REFERENTIALLY STABLE callback (state setter or store action — never an
   * inline closure): it is an effect dependency, so a per-render identity
   * would tear down and re-run the publish effect on every render.
   */
  readonly onSelectionChange: (selection: ImportSelection | null) => void;
}

/**
 * Publishes the selection upward; the panel performs NO commit itself — the
 * modal commits for existing novels, the wizard commits at Step-5 completion.
 * Both route the published selection through buildAdjustments (F1 T7), so the
 * publish is v2-complete in EVERY state:
 *
 * - Provisional (pick time, preview pending): empty items + EMPTY_OPS —
 *   buildAdjustments yields the identity payload; safe because the commit
 *   endpoint re-parses and re-validates the raw files server-side.
 * - Preview resolved (v2 AND v1 servers): the simulated rows bind the stable
 *   keys. On a v1 server the ops UI is gated off, so ops stay EMPTY_OPS and
 *   rows are one `#0` part per chapter — final == original space, i.e. exact
 *   v1 semantics, expressed in the same v2 vocabulary.
 *
 * A preview failure retracts the selection (null), so nothing can be
 * committed off an unanalyzed preview.
 */
export function useSelectionPublish({
  files,
  preview,
  ops,
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
      // Provisional pick-time publish: identity adjustments at commit.
      onSelectionChange({
        files,
        items: [],
        ops: EMPTY_OPS,
        excludedKeys: [],
        titleByKey: {},
        includedCount: files.length,
      });
      return;
    }
    onSelectionChange({
      files,
      items: preview.items,
      ops,
      excludedKeys: [...excludedKeys],
      titleByKey,
      includedCount: rows.filter((row) => !excludedKeys.has(row.key)).length,
    });
  }, [files, preview, ops, excludedKeys, titleByKey, rows, onSelectionChange]);
}
