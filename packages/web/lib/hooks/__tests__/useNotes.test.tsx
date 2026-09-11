/**
 * useNotes hook tests (NOTES-001) — MSW-backed read + invalidation cycle.
 *
 * Conventions: centralized setupTests.ts neutralizes motion and returns
 * i18n keys; the MSW guard requires handlers for every request made.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { server } from "@/mocks/server";
import { useCreateNote, useNotes, useNoteTags } from "../useNotes";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe("useNotes", () => {
  it("fetches the filtered note list", async () => {
    server.use(
      http.get("*/api/v1/notes", ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get("note_type")).toBe("idea");
        return HttpResponse.json([
          {
            id: "n1",
            title: null,
            content: "first line\nbody",
            note_type: "idea",
            tags: ["plot"],
            novel_id: null,
            series_id: null,
            created_at: "2026-08-21T00:00:00Z",
            updated_at: "2026-08-21T00:00:00Z",
          },
        ]);
      }),
    );

    const { result } = renderHook(() => useNotes({ note_type: "idea" }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.[0]?.note_type).toBe("idea");
  });

  it("keeps the previous list visible while a changed filter refetches (follow-up P-FE3)", async () => {
    server.use(
      http.get("*/api/v1/notes", ({ request }) => {
        const type = new URL(request.url).searchParams.get("note_type");
        return HttpResponse.json(
          type === "question"
            ? [
                {
                  id: "n2",
                  title: null,
                  content: "question note",
                  note_type: "question",
                  tags: [],
                  novel_id: null,
                  series_id: null,
                  created_at: "2026-08-21T00:00:00Z",
                  updated_at: "2026-08-21T00:00:00Z",
                },
              ]
            : [
                {
                  id: "n1",
                  title: null,
                  content: "idea note",
                  note_type: "idea",
                  tags: [],
                  novel_id: null,
                  series_id: null,
                  created_at: "2026-08-21T00:00:00Z",
                  updated_at: "2026-08-21T00:00:00Z",
                },
              ],
        );
      }),
    );

    const { result, rerender } = renderHook(({ type }) => useNotes({ note_type: type }), {
      initialProps: { type: "idea" as "idea" | "question" },
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.data?.[0]?.id).toBe("n1"));

    rerender({ type: "question" });

    // Synchronously after the key change the OLD list stays visible as
    // placeholder data — no loading pulse between filter refetches.
    expect(result.current.isPlaceholderData).toBe(true);
    expect(result.current.data?.[0]?.id).toBe("n1");
    await waitFor(() => expect(result.current.data?.[0]?.id).toBe("n2"));
    expect(result.current.isPlaceholderData).toBe(false);
  });
});

describe("useNoteTags", () => {
  it("fetches distinct tags with prefix", async () => {
    server.use(
      http.get("*/api/v1/notes/tags", ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get("q")).toBe("pl");
        return HttpResponse.json({ tags: ["plot"] });
      }),
    );

    const { result } = renderHook(() => useNoteTags("pl"), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.data?.tags).toEqual(["plot"]));
  });
});

describe("useCreateNote invalidation", () => {
  it("invalidates the notes list after create", async () => {
    let listCalls = 0;
    server.use(
      http.get("*/api/v1/notes", () => {
        listCalls += 1;
        return HttpResponse.json([]);
      }),
      http.post("*/api/v1/notes", async () =>
        HttpResponse.json(
          {
            id: "n2",
            title: null,
            content: "captured",
            note_type: "idea",
            tags: [],
            novel_id: null,
            series_id: null,
            created_at: "2026-08-21T00:00:00Z",
            updated_at: "2026-08-21T00:00:00Z",
          },
          { status: 201 },
        ),
      ),
    );

    const wrapper = createWrapper();
    renderHook(() => useNotes(), { wrapper });
    await waitFor(() => expect(listCalls).toBeGreaterThanOrEqual(1));

    const create = renderHook(() => useCreateNote(), { wrapper });
    await act(async () => {
      await create.result.current.mutateAsync({ content: "captured" });
    });

    await waitFor(() => expect(listCalls).toBeGreaterThanOrEqual(2));
  });
});
