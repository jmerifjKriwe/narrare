/**
 * Tests for the import modal (commit + invalidation + failure retry path).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

function renderModal(open = true) {
  const client = new QueryClient();
  const onOpenChange = vi.fn();
  render(
    <QueryClientProvider client={client}>
      <ImportModal novelId="novel-1" open={open} onOpenChange={onOpenChange} />
    </QueryClientProvider>,
  );
  return { onOpenChange, client };
}

describe("ImportModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it("clears the failure flag and closes on successful commit", async () => {
    sessionStorage.setItem("narrare:importFailed:novel-1", "1");
    vi.mocked(importApi.commit).mockResolvedValueOnce({
      novel_id: "novel-1",
      created_count: 2,
      first_position: 0,
      last_position: 1,
      chapters: [],
    });
    const { onOpenChange } = renderModal();

    // Select a file through the embedded panel
    const input = screen.getByLabelText(/choose files/i) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["# A\nb"], "a.md")] } });

    const confirm = await screen.findByRole("button", { name: /import/i });
    fireEvent.click(confirm);

    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
    expect(sessionStorage.getItem("narrare:importFailed:novel-1")).toBeNull();
    expect(importApi.commit).toHaveBeenCalledWith([expect.any(File)], "novel-1", {
      excluded_indices: [],
      title_overrides: {},
    });
  });

  it("keeps the modal open with the error on commit failure", async () => {
    vi.mocked(importApi.commit).mockRejectedValueOnce(new Error("boom"));
    renderModal();

    const input = screen.getByLabelText(/choose files/i) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["# A\nb"], "a.md")] } });

    fireEvent.click(await screen.findByRole("button", { name: /import/i }));
    expect(await screen.findByText(/boom/)).toBeInTheDocument();
  });
});
