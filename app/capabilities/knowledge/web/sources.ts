/**
 * The sources archive's pure helpers (W5 Task 6) — the upload's client-side
 * refusals mirrored from the service's own contract, the byte size in the
 * reader's regional format, and the extension summary the document list's
 * meta line derives from the REAL titles.
 *
 * The ingestion decodes plain text as UTF-8 (router.upload_document) and
 * refuses anything over MAX_UPLOAD_BYTES with a 413. The picker meets both
 * bounds before the wire does — a refused file is never sent, and the
 * refusal names the bound it crossed. The server's own 413/422 still answer
 * through the mutation's error face (a file can shrink or grow between the
 * check and the send, and the empty-document refusal is the server's to
 * make).
 */
import { formatNumber } from "@shell/lib/format";

/** The service's ceiling (knowledge/service.py MAX_UPLOAD_BYTES), mirrored
 *  so the writer meets the refusal before the wire does. Decimal, like the
 *  server's own million. */
export const MAX_UPLOAD_BYTES = 1_000_000;

/** The text kinds the ingestion accepts: a text MIME (the browser's own
 *  classification, extensionless files included) or one of the plain-text
 *  extensions the corpus speaks. A PDF is binary — the decoder would ingest
 *  replacement-character noise, so the picker refuses it honestly instead. */
export function isTextFile(file: { name: string; type: string }): boolean {
  if (file.type.startsWith("text/")) return true;
  const dot = file.name.lastIndexOf(".");
  if (dot < 0) return false;
  const extension = file.name.slice(dot + 1).toLowerCase();
  return extension === "txt" || extension === "md" || extension === "markdown";
}

/** A byte size on the decimal ladder the server's limit speaks (KB = 1000),
 *  at most one decimal and no trailing zero — the reader's regional number
 *  format, the shell's own seam. */
export function formatBytes(bytes: number): string {
  if (bytes < 1000) return `${formatNumber(bytes)} B`;
  if (bytes < 1_000_000) return `${formatNumber(bytes / 1000, { maximumFractionDigits: 1 })} KB`;
  return `${formatNumber(bytes / 1_000_000, { maximumFractionDigits: 1 })} MB`;
}

/** The distinct extensions the real titles carry, sorted and lowercased —
 *  the list meta's „(.pdf, .txt, .md)" derived, never invented. A suffix
 *  only counts when it reads as one: short, alphanumeric, after a dot that
 *  is neither leading nor trailing („Band 1. Die lange Reise" carries
 *  none). */
export function titleExtensions(titles: readonly string[]): string[] {
  const extensions = new Set<string>();
  for (const title of titles) {
    const dot = title.lastIndexOf(".");
    if (dot <= 0 || dot === title.length - 1) continue;
    const extension = title.slice(dot + 1).toLowerCase();
    if (extension.length <= 5 && /^[a-z0-9]+$/.test(extension)) extensions.add(extension);
  }
  return [...extensions].sort();
}
