import { client } from "@shell/lib/api/client";
import type { components } from "@shell/lib/api/schema";

/**
 * The shelf's two interchange calls. The export endpoint answers with two
 * different bodies under one URL — a JSON receipt for a path export, ZIP
 * bytes for a ZIP export — so the typed client (which reads the 200 as
 * JSON alone) is not the honest door for it: the call goes out raw, and
 * the mode decides how the answer is read. The import endpoint speaks
 * multipart through the typed client, the same one-cast shape the
 * knowledge document upload uses.
 */
export type ExportMode = "path" | "zip";
export type ExportReceipt = components["schemas"]["ExportDone"];
export type ImportReport = components["schemas"]["ImportReportRead"];

/** The ZIP answer: the bytes for the browser's download seam, and the name
 *  the Content-Disposition proposed — or the caller's slug-based fallback. */
export type ZipDownload = { blob: Blob; filename: string };

/**
 * A refusal that keeps what the UI needs to name itself: the status line
 * and, when the body carried one, the machine-readable detail. `detail`
 * is untrusted-shaped data (codes, archive-supplied file names) — the
 * dialogs localize by code and render the strings as text.
 */
export type InterchangeFailure = Error & { status: number; detail: unknown };

function failure(status: number, detail: unknown, message: string): InterchangeFailure {
  return Object.assign(new Error(message), { status, detail });
}

/** The `detail` member of a refusal body, for dialogs that localize by code. */
export function detailOf(error: unknown): unknown {
  return (error as InterchangeFailure | null | undefined)?.detail;
}

/**
 * A slug in the archive format's spirit: lowercase, ASCII-folded,
 * non-alphanumerics to `-`, trimmed, empty falls back to `untitled`.
 * PROPOSAL ONLY — the server derives the archive's own names, and this
 * client-side rule deliberately does not chase byte parity with it (it
 * strips combining marks where the server drops non-ASCII, so "Straße"
 * proposes `stra-e` where the server would say `strae`). The prefill only
 * needs to be a sensible folder name the user can edit.
 */
export function slugify(text: string): string {
  const folded = text.normalize("NFKD").replace(/\p{M}/gu, "");
  const slug = folded
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug !== "" ? slug : "untitled";
}

const pad2 = (value: number): string => String(value).padStart(2, "0");

/**
 * The export dialog's prefilled path: `<slug>-<yyyymmdd-hhmm>`. The
 * timestamp makes the common export land on a fresh folder name, so the
 * refusal on non-empty targets (D10) stays visible without standing in
 * the common path's way.
 */
export function proposeExportPath(title: string, now: Date = new Date()): string {
  const stamp =
    `${now.getFullYear()}${pad2(now.getMonth() + 1)}${pad2(now.getDate())}` +
    `-${pad2(now.getHours())}${pad2(now.getMinutes())}`;
  return `${slugify(title)}-${stamp}`;
}

/** The name inside `attachment; filename="…"`, when the header carries one. */
function filenameFromDisposition(header: string | null): string | null {
  if (header === null) return null;
  return /filename="([^"]+)"/.exec(header)?.[1] ?? null;
}

/**
 * Export a novel into a directory on disk, or as a ZIP download. The path
 * mode's answer is the receipt (`{path, chapters, entities}`); the ZIP
 * mode's answer is the bytes — never parsed as the JSON receipt it is not.
 * Refusals (404, 409 `target_not_empty`, 422 field contract) throw an
 * `InterchangeFailure` carrying status and detail.
 */
export async function exportNovel(
  novelId: string,
  mode: ExportMode,
  path?: string,
  fallbackFilename = "untitled.zip",
): Promise<ExportReceipt | ZipDownload> {
  const response = await fetch(`/api/writing/novels/${encodeURIComponent(novelId)}/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(mode === "path" ? { mode, path } : { mode }),
  });
  if (!response.ok) {
    let detail: unknown = undefined;
    try {
      const body = (await response.json()) as { detail?: unknown } | null;
      detail = body?.detail;
    } catch {
      // a bare status line (a proxy's 502): the refusal is the status alone
    }
    throw failure(response.status, detail, `export refused: ${response.status}`);
  }
  if (mode === "zip") {
    const blob = await response.blob();
    return {
      blob,
      filename:
        filenameFromDisposition(response.headers.get("content-disposition")) ?? fallbackFilename,
    };
  }
  return (await response.json()) as ExportReceipt;
}

/** The import's source: an uploaded archive file or a server-side path —
 *  exactly one; the dialog enforces it, the server re-validates. */
export type ImportInput = { file?: File; path?: string; novelId?: string };

/**
 * Import one archive as a new novel (`novelId` absent) or merged into an
 * existing one. Multipart through the typed client; openapi-typescript
 * renders the binary part as `string`, which real FormData is not — one
 * cast, the same shape the knowledge document upload uses. The 201 report
 * comes back whole; every refusal throws an `InterchangeFailure`.
 */
export async function importArchive(input: ImportInput): Promise<ImportReport> {
  const body = new FormData();
  if (input.file !== undefined) body.append("archive", input.file);
  if (input.path !== undefined) body.append("path", input.path);
  if (input.novelId !== undefined) body.append("novel_id", input.novelId);
  const { data, error, response } = await client.POST("/api/writing/novels/import", {
    body: body as unknown as components["schemas"]["Body_import_novel_api_writing_novels_import_post"],
  });
  if (!response.ok || !data) {
    const detail = (error as { detail?: unknown } | null | undefined)?.detail;
    throw failure(response.status, detail, `import refused: ${response.status}`);
  }
  return data;
}

/**
 * Hand a blob to the browser as a download: a temporary anchor with the
 * `download` attribute, clicked once, removed, its object URL revoked — the
 * archive lives in the user's Downloads folder, not on the page. The revoke
 * is deferred one task: the navigation reads the URL asynchronously, and a
 * revoke in the click's own turn can outrun the download it served.
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
