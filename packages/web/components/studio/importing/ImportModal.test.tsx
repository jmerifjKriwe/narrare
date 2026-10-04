/**
 * Tests for the import modal (commit + invalidation + failure retry path +
 * the post-commit extraction CTA card, F2 T8 / ADR-092 spec §8.1).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ImportModal } from "./ImportModal";

// The centralized setupTests.ts next-intl mock returns i18n KEY STRINGS, but
// these tests assert rendered copy (e.g. /choose files/i, /boom/), so the real
// "importing" catalog is served through real next-intl instead — the same
// createTranslator pattern used by SeriesDriftPanel.test.tsx.
vi.mock("next-intl", async () => {
  const actual = await vi.importActual<typeof import("next-intl")>("next-intl");
  const importing = (await import("../../../../i18n/messages/en/importing.json")).default;
  return {
    ...actual,
    useTranslations: () =>
      actual.createTranslator({ locale: "en", messages: { importing }, namespace: "importing" }),
  };
});

vi.mock("@/lib/api/client", () => ({
  importApi: {
    preview: vi.fn(),
    commit: vi.fn(),
  },
}));

import { importApi } from "@/lib/api/client";

const COMMIT_WITH_TWO_CHAPTERS = {
  novel_id: "novel-1",
  created_count: 2,
  first_position: 0,
  last_position: 1,
  chapters: [
    { id: "c1", title: "One", position: 1, word_count: 20 },
    { id: "c2", title: "Two", position: 2, word_count: 14 },
  ],
};

function renderModal(onExtract?: (chapterIds: string[]) => void) {
  const client = new QueryClient();
  const onOpenChange = vi.fn();
  render(
    <QueryClientProvider client={client}>
      <ImportModal
        novelId="novel-1"
        open={true}
        onOpenChange={onOpenChange}
        onExtract={onExtract}
      />
    </QueryClientProvider>,
  );
  return { onOpenChange, client };
}

async function commitThroughUi() {
  const input = screen.getByLabelText(/choose files/i) as HTMLInputElement;
  fireEvent.change(input, { target: { files: [new File(["# A\nb"], "a.md")] } });
  fireEvent.click(await screen.findByRole("button", { name: /import/i }));
}

describe("ImportModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it("clears the failure flag, invalidates, and shows the success cost card after commit", async () => {
    sessionStorage.setItem("narrare:importFailed:novel-1", "1");
    vi.mocked(importApi.commit).mockResolvedValueOnce(COMMIT_WITH_TWO_CHAPTERS);
    const { onOpenChange, client } = renderModal(vi.fn());
    // Invalidation contract: the chapters query of THIS novel is refetched.
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    await commitThroughUi();

    // Success card (D9a, spec §8.1): cost transparency + both actions, and the
    // dialog stays open — closing is now the user's explicit choice.
    expect(await screen.findByTestId("import-success-card")).toBeInTheDocument();
    expect(screen.getByText("2 chapters imported")).toBeInTheDocument();
    expect(screen.getByText("2 chapters · 34 words · 2 AI calls")).toBeInTheDocument();
    expect(screen.getByTestId("import-extract-btn")).toBeInTheDocument();
    expect(screen.getByTestId("import-notnow-btn")).toBeInTheDocument();
    expect(onOpenChange).not.toHaveBeenCalled();

    // Contract cleanup unchanged by the CTA: failed flag cleared + invalidation.
    expect(sessionStorage.getItem("narrare:importFailed:novel-1")).toBeNull();
    expect(importApi.commit).toHaveBeenCalledWith([expect.any(File)], "novel-1", {
      splits: [],
      merges: [],
      excluded_indices: [],
      title_overrides: {},
    });
    expect(invalidateSpy.mock.calls[0][0]).toEqual({
      queryKey: ["novels", "novel-1", "chapters"],
    });
  });

  it("Extract to Knowledge Base closes the modal and hands the chapter ids to the parent", async () => {
    vi.mocked(importApi.commit).mockResolvedValueOnce(COMMIT_WITH_TWO_CHAPTERS);
    const onExtract = vi.fn();
    const { onOpenChange } = renderModal(onExtract);

    await commitThroughUi();
    fireEvent.click(await screen.findByTestId("import-extract-btn"));

    expect(onOpenChange).toHaveBeenCalledWith(false);
    // Panel seed: exactly the committed chapters, in commit order.
    expect(onExtract).toHaveBeenCalledWith(["c1", "c2"]);
  });

  it("Not now closes the modal without starting extraction", async () => {
    vi.mocked(importApi.commit).mockResolvedValueOnce(COMMIT_WITH_TWO_CHAPTERS);
    const onExtract = vi.fn();
    const { onOpenChange } = renderModal(onExtract);

    await commitThroughUi();
    fireEvent.click(await screen.findByTestId("import-notnow-btn"));

    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(onExtract).not.toHaveBeenCalled();
  });

  it("keeps the modal open with the error on commit failure", async () => {
    vi.mocked(importApi.commit).mockRejectedValueOnce(new Error("boom"));
    const { onOpenChange } = renderModal();

    await commitThroughUi();
    expect(await screen.findByText(/boom/)).toBeInTheDocument();
    // Failure keeps the dialog open for retry — never closes, no success card.
    expect(onOpenChange).not.toHaveBeenCalled();
    expect(screen.queryByTestId("import-success-card")).not.toBeInTheDocument();
  });
});
