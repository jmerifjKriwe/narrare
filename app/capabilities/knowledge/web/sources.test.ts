/**
 * The sources archive's pure helpers (W5 Task 6) — the upload's client-side
 * refusals mirrored from the service's own contract (plain text, 1 MB), the
 * byte size in the reader's regional format, and the extension summary the
 * document list's meta line derives from the REAL titles.
 */
import { beforeEach, describe, expect, it } from "vitest";

import { applyLocale } from "@shell/lib/locale";

import { formatBytes, isTextFile, MAX_UPLOAD_BYTES, titleExtensions } from "./sources";

beforeEach(() => {
  // The number format is the reader's regional one — pinned to the source
  // locale so the ladder's spellings are deterministic.
  applyLocale("en");
});

describe("the upload's bounds mirror the service's contract", () => {
  it("the ceiling is the service's own million bytes", () => {
    expect(MAX_UPLOAD_BYTES).toBe(1_000_000);
  });

  it("text kinds pass — by extension or by MIME, case-insensitive", () => {
    expect(isTextFile({ name: "Notizen.txt", type: "text/plain" })).toBe(true);
    expect(isTextFile({ name: "Funkprotokolle.MD", type: "" })).toBe(true);
    expect(isTextFile({ name: "notes.markdown", type: "" })).toBe(true);
    // A text MIME carries an extensionless file too.
    expect(isTextFile({ name: "README", type: "text/plain" })).toBe(true);
    expect(isTextFile({ name: "daten.csv", type: "text/csv" })).toBe(true);
  });

  it("binary kinds are refused — the ingestion decodes plain text only", () => {
    expect(isTextFile({ name: "Survey.pdf", type: "application/pdf" })).toBe(false);
    expect(isTextFile({ name: "bild.png", type: "image/png" })).toBe(false);
    expect(isTextFile({ name: "archiv.zip", type: "application/zip" })).toBe(false);
    expect(isTextFile({ name: "ohneendung", type: "" })).toBe(false);
  });
});

describe("the byte size reads in the reader's regional format", () => {
  it("small sizes stay in bytes, larger ones climb the decimal ladder", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(999)).toBe("999 B");
    expect(formatBytes(38_000)).toBe("38 KB");
    expect(formatBytes(124_000)).toBe("124 KB");
    expect(formatBytes(4_200_000)).toBe("4.2 MB");
    // One decimal at most, and no trailing zero — 1 MB, not 1.0 MB.
    expect(formatBytes(1_000_000)).toBe("1 MB");
  });
});

describe("the extension summary comes from the real titles", () => {
  it("collects the distinct suffixes, sorted and lowercased", () => {
    expect(
      titleExtensions([
        "Groom Lake Deep Core Survey (USGS-1983-B).pdf",
        "Notizen zu Station 7 & Permafrost.txt",
        "Funkprotokolle 2094.md",
        "Noch eine Notiz.TXT",
      ]),
    ).toEqual(["md", "pdf", "txt"]);
  });

  it("a title without a usable suffix contributes nothing — no invented extension", () => {
    expect(titleExtensions(["Band 1. Die lange Reise", "Notizen", "leer."])).toEqual([]);
    expect(titleExtensions([])).toEqual([]);
  });
});
