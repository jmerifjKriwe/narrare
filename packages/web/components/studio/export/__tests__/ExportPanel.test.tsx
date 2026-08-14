/**
 * ExportPanel component tests (IO-001 / ADR-081).
 *
 * The panel is presentation-only (RULE-06): useExportPanel is the controller.
 * We mock the hook and drive each visual state:
 *   1. Renders title + format cards
 *   2. Disables unavailable formats + shows the unavailable label
 *   3. Format selection calls setOptions with the new format
 *   4. Idle → Export button calls handleExport
 *   5–7. Polling states: pending / running / completed
 *   8.  completed → Download button calls handleDownload
 *   9.  failed → error surfaces + start-new calls startNewExport
 *   10. createFailed → create error surfaces
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ExportPanel } from "@/components/studio/export/ExportPanel";
import type { ExportJob, ExportOptions } from "@/types";

// ── Mocks ────────────────────────────────────────────────────────────────

const baseOptions: ExportOptions = {
  format: "pdf",
  volume_id: null,
  include_front_matter: true,
  include_back_matter: true,
  include_summaries: false,
  include_character_list: false,
  include_location_glossary: false,
  pdf_options: {
    paper_size: "b-format-129x198",
    margins: null,
    body_size_pt: 11,
    leading_ratio: 1.2,
    drop_caps: false,
    include_toc: true,
  },
  epub_options: { cover_image_path: null, css: null },
  markdown_options: { chapter_heading_level: 1, include_front_matter: true },
};

function makeJob(overrides: Partial<ExportJob> = {}): ExportJob {
  return {
    job_id: "job-1",
    novel_id: "00000000-0000-0000-0000-000000000001",
    format: "pdf",
    status: "pending",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    artifact_url: null,
    error: null,
    ...overrides,
  };
}

const panelReturn = {
  formats: [
    { format: "pdf" as const, available: true },
    { format: "epub" as const, available: true },
    { format: "md" as const, available: false },
  ],
  formatsLoading: false,
  formatsFailed: false,
  isFormatAvailable: (f: string) => f !== "md",
  options: baseOptions,
  setOptions: vi.fn(),
  job: undefined as ExportJob | undefined,
  isExporting: false,
  createFailed: false,
  handleExport: vi.fn(),
  handleDownload: vi.fn(),
  downloadPending: false,
  downloadFailed: false,
  startNewExport: vi.fn(),
};

vi.mock("@/components/studio/export/useExportPanel", () => ({
  useExportPanel: () => panelReturn,
}));

function renderPanel() {
  return render(<ExportPanel novelId="novel-1" isOpen onClose={() => {}} />);
}

// ── Tests ────────────────────────────────────────────────────────────────

describe("ExportPanel", () => {
  beforeEach(() => {
    Object.assign(panelReturn, {
      formatsLoading: false,
      formatsFailed: false,
      options: baseOptions,
      job: undefined,
      isExporting: false,
      createFailed: false,
      downloadPending: false,
      downloadFailed: false,
    });
    panelReturn.setOptions = vi.fn();
    panelReturn.handleExport = vi.fn();
    panelReturn.handleDownload = vi.fn();
    panelReturn.startNewExport = vi.fn();
  });

  it("renders the panel title + format cards", () => {
    renderPanel();
    expect(screen.getByText("title")).toBeInTheDocument();
    expect(screen.getByTestId("format-pdf")).toBeInTheDocument();
    expect(screen.getByTestId("format-epub")).toBeInTheDocument();
    expect(screen.getByTestId("format-md")).toBeInTheDocument();
  });

  it("disables the unavailable format and shows the unavailable label", () => {
    renderPanel();
    const mdCard = screen.getByTestId("format-md");
    expect(mdCard).toBeDisabled();
    expect(screen.getByText("format.unavailable")).toBeInTheDocument();
  });

  it("calls setOptions with the new format when a card is clicked", () => {
    renderPanel();
    fireEvent.click(screen.getByTestId("format-epub"));
    expect(panelReturn.setOptions).toHaveBeenCalledWith(
      expect.objectContaining({ format: "epub" }),
    );
  });

  it("shows the Export button and calls handleExport on click (idle)", () => {
    renderPanel();
    const submit = screen.getByTestId("export-submit");
    expect(submit).toBeInTheDocument();
    fireEvent.click(submit);
    expect(panelReturn.handleExport).toHaveBeenCalledOnce();
  });

  it("shows the pending status while the job is queued", () => {
    panelReturn.job = makeJob({ status: "pending" });
    renderPanel();
    expect(screen.getByTestId("export-job-status")).toBeInTheDocument();
    expect(screen.getByText("status.pending")).toBeInTheDocument();
  });

  it("shows the running status while the job renders", () => {
    panelReturn.job = makeJob({ status: "running" });
    renderPanel();
    expect(screen.getByText("status.running")).toBeInTheDocument();
  });

  it("shows a Download button when the job completes and downloads on click", () => {
    panelReturn.job = makeJob({ status: "completed", artifact_url: "/x?token=t" });
    renderPanel();
    const download = screen.getByTestId("export-download");
    expect(download).toBeInTheDocument();
    fireEvent.click(download);
    expect(panelReturn.handleDownload).toHaveBeenCalledOnce();
  });

  it("surfaces the failure error and offers a new export on failed", () => {
    panelReturn.job = makeJob({ status: "failed", error: "typst missing" });
    renderPanel();
    expect(screen.getByText("status.failed")).toBeInTheDocument();
    expect(screen.getByText("status.errorPrefix")).toBeInTheDocument();
    fireEvent.click(screen.getByText("status.startNew"));
    expect(panelReturn.startNewExport).toHaveBeenCalledOnce();
  });

  it("surfaces a create error when the export could not start", () => {
    panelReturn.createFailed = true;
    renderPanel();
    expect(screen.getByTestId("export-create-error")).toBeInTheDocument();
    expect(screen.getByText("errors.createFailed")).toBeInTheDocument();
  });
});
