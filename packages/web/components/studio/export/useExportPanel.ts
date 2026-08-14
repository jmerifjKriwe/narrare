"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { exportApi, parseArtifactToken } from "@/lib/api/export";
import type { ExportFormat, ExportJob, ExportOptions } from "@/types";
import { useExportSettings } from "./useExportSettings";

/**
 * Trigger a browser download for a Blob. Pure-DOM concern (RULE-06: kept out
 * of the API client). Revoke the object URL after the click to avoid leaks.
 */
function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

/**
 * useExportPanel — the IO-001 export state controller.
 *
 * Owns: the format-availability query, the remembered export options, the
 * create-job mutation, the poll-until-terminal job query, and the single-use
 * artifact download. Kept as a hook (RULE-06) so the ExportPanel component
 * stays presentation-only.
 *
 * Polling: TanStack Query `refetchInterval` as a function — 1.5s while PENDING,
 * 3s while RUNNING, and disabled (returns false) once the job reaches a
 * terminal state (COMPLETED / FAILED). Cleanup is automatic on unmount.
 */
export function useExportPanel(novelId: string): {
  readonly formats: readonly { format: ExportFormat; available: boolean }[] | undefined;
  readonly formatsLoading: boolean;
  readonly formatsFailed: boolean;
  readonly isFormatAvailable: (format: ExportFormat) => boolean;
  readonly options: ExportOptions;
  readonly setOptions: (next: ExportOptions) => void;
  readonly job: ExportJob | undefined;
  readonly isExporting: boolean;
  readonly createFailed: boolean;
  readonly handleExport: () => void;
  readonly handleDownload: () => void;
  readonly downloadPending: boolean;
  readonly downloadFailed: boolean;
  readonly startNewExport: () => void;
} {
  const { options, setOptions } = useExportSettings();

  // 1. Format availability (disable unavailable formats before Export click).
  const formatsQuery = useQuery({
    queryKey: ["export", "formats"],
    queryFn: exportApi.listFormats,
    staleTime: 60_000,
  });

  const isFormatAvailable = useCallback(
    (format: ExportFormat): boolean => {
      const row = formatsQuery.data?.find((f) => f.format === format);
      // Unknown availability (query still loading) → do NOT block the user.
      return row ? row.available : true;
    },
    [formatsQuery.data],
  );

  // 2. Active job id (set by the create mutation; cleared on "new export").
  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  // 3. Poll the job until terminal. refetchInterval as a function gives
  //    status-aware cadence + automatic stop on COMPLETED / FAILED.
  const jobQuery = useQuery({
    queryKey: ["export", "job", activeJobId],
    queryFn: () => exportApi.getJob(activeJobId as string),
    enabled: !!activeJobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "completed" || status === "failed") return false;
      return status === "pending" ? 1500 : 3000;
    },
  });

  // 4. Create + dispatch.
  const createMutation = useMutation({
    mutationFn: () => exportApi.createExport(novelId, options),
    onSuccess: (job) => setActiveJobId(job.job_id),
  });

  // 5. Single-use artifact download.
  const downloadMutation = useMutation({
    mutationFn: async () => {
      const job = jobQuery.data;
      const token = parseArtifactToken(job?.artifact_url ?? null);
      if (!token || !job) throw new Error("no-artifact");
      return exportApi.downloadArtifact(job.job_id, token);
    },
    onSuccess: ({ blob, filename }) => triggerDownload(blob, filename),
  });

  const startNewExport = useCallback(() => {
    setActiveJobId(null);
    createMutation.reset();
    downloadMutation.reset();
  }, [createMutation, downloadMutation]);

  return {
    formats: formatsQuery.data,
    formatsLoading: formatsQuery.isLoading,
    formatsFailed: formatsQuery.isError,
    isFormatAvailable,
    options,
    setOptions,
    job: jobQuery.data,
    isExporting: createMutation.isPending || jobQuery.isFetching,
    createFailed: createMutation.isError,
    handleExport: () => createMutation.mutate(),
    handleDownload: () => downloadMutation.mutate(),
    downloadPending: downloadMutation.isPending,
    downloadFailed: downloadMutation.isError,
    startNewExport,
  };
}
