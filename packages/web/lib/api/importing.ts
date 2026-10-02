/**
 * Project Import API — stateless two-phase multipart (ADR-091).
 */

import type { ImportCommitAdjustments, ImportCommitResponse, ImportPreviewResponse } from "@/types";
import { fetchApiUpload } from "./core";

function filesBody(files: File[]): FormData {
  const body = new FormData();
  for (const file of files) body.append("files", file);
  return body;
}

export const importApi = {
  preview: (files: File[]) =>
    fetchApiUpload<ImportPreviewResponse>("/import/preview", { body: filesBody(files) }),

  commit: (files: File[], novelId: string, adjustments: ImportCommitAdjustments) => {
    const body = filesBody(files);
    body.append("novel_id", novelId);
    body.append("adjustments", JSON.stringify(adjustments));
    return fetchApiUpload<ImportCommitResponse>("/import/commit", { body });
  },
};
