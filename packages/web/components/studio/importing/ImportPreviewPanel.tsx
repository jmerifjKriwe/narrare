"use client";

import { useTranslations } from "next-intl";
import { useCallback, useRef, useState } from "react";
import { importApi } from "@/lib/api/client";
import type { ImportPreviewResponse, ImportSelection } from "@/types";

/**
 * Shared import surface: pick files → server preview → per-chapter title
 * edit + include/exclude. Publishes the full selection upward; performs NO
 * commit itself (the modal commits for existing novels, the wizard commits
 * at Step-5 completion) — ADR-091 / spec §6.1.
 *
 * Selection lifecycle: a provisional selection (one chapter per picked file)
 * is published at pick time and refined with the authoritative server counts
 * once the preview resolves; a preview failure retracts it (null), so nothing
 * can be committed off an unanalyzed preview. The commit endpoint re-parses
 * and re-validates the raw files server-side, so the provisional window is
 * safe.
 */
interface ImportPreviewPanelProps {
  readonly onSelectionChange: (selection: ImportSelection | null) => void;
}

export function ImportPreviewPanel({ onSelectionChange }: ImportPreviewPanelProps) {
  const t = useTranslations("importing");
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [excluded, setExcluded] = useState<Set<number>>(new Set());
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const publish = useCallback(
    (
      nextFiles: File[],
      nextExcluded: Set<number>,
      nextOverrides: Record<string, string>,
      chapterCount: number,
    ) => {
      if (nextFiles.length === 0 || chapterCount === 0) {
        onSelectionChange(null);
        return;
      }
      onSelectionChange({
        files: nextFiles,
        excludedIndices: [...nextExcluded],
        titleOverrides: nextOverrides,
        includedCount: chapterCount - nextExcluded.size,
      });
    },
    [onSelectionChange],
  );

  const handleFiles = async (picked: FileList | null) => {
    if (!picked || picked.length === 0) return;
    // Deterministic order BEFORE upload — the server never re-orders (spec §5.1)
    const sorted = [...picked].sort((a, b) =>
      a.name.localeCompare(b.name, undefined, { numeric: true }),
    );
    setFiles(sorted);
    setExcluded(new Set());
    setOverrides({});
    setError(null);
    setPreview(null);
    // Provisional selection (see doc comment) — refined/retracted below.
    publish(sorted, new Set(), {}, sorted.length);
    setIsLoading(true);
    try {
      const result = await importApi.preview(sorted);
      if (!result) return;
      setPreview(result);
      publish(sorted, new Set(), {}, result.chapter_count);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      onSelectionChange(null);
    } finally {
      setIsLoading(false);
    }
  };

  const toggle = (index: number) => {
    const next = new Set(excluded);
    if (next.has(index)) next.delete(index);
    else next.add(index);
    setExcluded(next);
    if (preview) publish(files, next, overrides, preview.chapter_count);
  };

  const rename = (index: number, title: string) => {
    const next = { ...overrides, [String(index)]: title };
    setOverrides(next);
    if (preview) publish(files, excluded, next, preview.chapter_count);
  };

  // Chapters of the same file share one file cell: the name renders on the
  // first chapter of each source-file group only (file-grouped list).
  const firstIndexPerFile = new Map<string, number>();
  if (preview) {
    for (const item of preview.items) {
      if (!firstIndexPerFile.has(item.source_file)) {
        firstIndexPerFile.set(item.source_file, item.index);
      }
    }
  }

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
              chapters: preview.chapter_count,
              words: preview.total_word_count.toLocaleString(),
            })}
          </p>
          <ul className="max-h-72 overflow-y-auto rounded-md border border-border">
            {preview.items.map((item) => {
              const currentTitle = overrides[String(item.index)] ?? item.suggested_title;
              return (
                <li
                  key={item.index}
                  className="flex items-center gap-2 border-b border-border/50 px-3 py-2 last:border-b-0"
                  data-testid={`import-preview-item-${item.index}`}
                >
                  <input
                    type="checkbox"
                    checked={!excluded.has(item.index)}
                    onChange={() => toggle(item.index)}
                    aria-label={t("column.include")}
                    className="h-4 w-4"
                  />
                  {/* Real <label> (not aria-label) so each title field is
                      named after ITS chapter for screen readers. */}
                  <label htmlFor={`import-chapter-title-${item.index}`} className="sr-only">
                    {currentTitle}
                  </label>
                  <input
                    id={`import-chapter-title-${item.index}`}
                    type="text"
                    value={currentTitle}
                    onChange={(e) => rename(item.index, e.target.value)}
                    className="min-w-0 flex-1 rounded border border-border bg-background px-2 py-1 text-sm"
                  />
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {t("column.words", { count: item.word_count })}
                  </span>
                  {firstIndexPerFile.get(item.source_file) === item.index && (
                    <span
                      className="shrink-0 max-w-32 truncate text-xs text-muted-foreground/70"
                      title={item.source_file}
                    >
                      {item.source_file}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </>
      )}
    </div>
  );
}
