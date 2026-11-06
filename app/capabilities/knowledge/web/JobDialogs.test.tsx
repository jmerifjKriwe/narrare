// @vitest-environment jsdom
/**
 * The palette's job dialogs: the extraction and the whole-novel check behind
 * a lazy dialog instead of the dock. Each dialog names its chapter or novel,
 * runs the trigger the dock panels already own, shows the job's progress
 * through `JobStatus`, and reports a refused enqueue in words — never a
 * silent close. A novel without chapters offers no trigger, only the named
 * absence the dock panel shows.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { t } from "@shell/lib/i18n";
import { queryClient } from "@shell/lib/query";

vi.mock("@shell/lib/api/client", () => ({
  client: {
    GET: vi.fn(),
    POST: vi.fn(),
    PATCH: vi.fn(),
    PUT: vi.fn(),
    DELETE: vi.fn(),
  },
}));

// The module under test does not exist yet: this file is the RED half.
import { client } from "@shell/lib/api/client";

import { ConsistencyCheckDialog, ExtractionJobDialog } from "./JobDialogs";

/** The client's methods as plain mocks; the real client's generics stay out. */
const api = client as unknown as Record<
  "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  ReturnType<typeof vi.fn>
>;

const NOVEL_ID = "6f1c2a52-9d3e-4f6e-8df5-7db9df0f4a52";
const CHAPTER_ID = "71bfa163-2c8f-4a6f-9e07-6f5f2c8d1b63";
const JOB_ID = "a8b2c3d4-5e6f-4a7b-8c9d-0e1f2a3b4c5d";

const CHAPTER = {
  id: CHAPTER_ID,
  novel_id: NOVEL_ID,
  title: "",
  position: 0,
  body: "Mira betrat das alte Haus am See.",
  created_at: "2026-10-30T09:00:00Z",
  updated_at: "2026-10-30T09:00:00Z",
};

function ok<T>(data: T, status = 200) {
  return { data, response: { ok: true, status } };
}

function refused(status: number) {
  return { data: undefined, response: { ok: false, status } };
}

function renderExtraction() {
  render(
    <QueryClientProvider client={queryClient}>
      <ExtractionJobDialog novelId={NOVEL_ID} isOpen onOpenChange={() => {}} />
    </QueryClientProvider>,
  );
}

function renderCheck() {
  render(
    <QueryClientProvider client={queryClient}>
      <ConsistencyCheckDialog novelId={NOVEL_ID} isOpen onOpenChange={() => {}} />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
});

describe("the palette's extraction dialog", () => {
  it("runs the chapter's extraction and reports the done count", async () => {
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/writing/novels/{novel_id}/chapters") return ok([CHAPTER]);
      if (path === "/api/jobs/{job_id}")
        return ok({
          id: JOB_ID,
          kind: "extract-entities",
          status: "done",
          progress: 100,
          result: { suggestions: 5 },
        });
      throw new Error(`unexpected GET ${path}`);
    });
    api.POST.mockResolvedValue(ok({ job_id: JOB_ID }, 202));
    renderExtraction();

    await userEvent.click(
      await screen.findByRole("button", { name: t("knowledge.extractChapter") }),
    );
    await waitFor(() => {
      expect(api.POST).toHaveBeenCalledWith("/api/knowledge/extraction/{novel_id}", {
        params: { path: { novel_id: NOVEL_ID } },
        body: { chapter_id: CHAPTER_ID },
      });
    });
    expect(
      await screen.findByText(t("jobs.done.extract-entities", { count: 5 })),
    ).toBeTruthy();
  });

  it("names a refused enqueue instead of closing silently", async () => {
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/writing/novels/{novel_id}/chapters") return ok([CHAPTER]);
      throw new Error(`unexpected GET ${path}`);
    });
    api.POST.mockResolvedValue(refused(409));
    renderExtraction();

    await userEvent.click(
      await screen.findByRole("button", { name: t("knowledge.extractChapter") }),
    );
    await waitFor(() => expect(api.POST).toHaveBeenCalled());
    expect(await screen.findByText(t("knowledge.extractionError"))).toBeTruthy();
  });

  it("offers no trigger without a chapter, only the named absence", async () => {
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/writing/novels/{novel_id}/chapters") return ok([]);
      throw new Error(`unexpected GET ${path}`);
    });
    renderExtraction();

    expect(await screen.findByText(t("knowledge.noActiveChapter"))).toBeTruthy();
    expect(
      screen.queryByRole("button", { name: t("knowledge.extractChapter") }),
    ).toBeNull();
    expect(api.POST).not.toHaveBeenCalled();
  });
});

describe("the palette's consistency-check dialog", () => {
  it("runs the whole-novel check and reports the done count", async () => {
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/jobs/{job_id}")
        return ok({
          id: JOB_ID,
          kind: "check-consistency",
          status: "done",
          progress: 100,
          result: { findings: 2 },
        });
      throw new Error(`unexpected GET ${path}`);
    });
    api.POST.mockResolvedValue(ok({ job_id: JOB_ID }, 202));
    renderCheck();

    await userEvent.click(await screen.findByRole("button", { name: t("knowledge.checkNovel") }));
    await waitFor(() => {
      expect(api.POST).toHaveBeenCalledWith("/api/knowledge/consistency/{novel_id}", {
        params: { path: { novel_id: NOVEL_ID } },
      });
    });
    expect(await screen.findByText(t("jobs.done.check-consistency", { count: 2 }))).toBeTruthy();
  });

  it("names a refused enqueue instead of closing silently", async () => {
    api.POST.mockResolvedValue(refused(409));
    renderCheck();

    await userEvent.click(await screen.findByRole("button", { name: t("knowledge.checkNovel") }));
    await waitFor(() => expect(api.POST).toHaveBeenCalled());
    expect(await screen.findByText(t("knowledge.checkError"))).toBeTruthy();
  });
});
