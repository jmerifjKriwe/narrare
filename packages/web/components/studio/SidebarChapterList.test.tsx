import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import enImporting from "../../../i18n/messages/en/importing.json";
import enStudio from "../../../i18n/messages/en/studio.json";
import { SidebarChapterList } from "./SidebarChapterList";

vi.mock("@/lib/api/client", () => ({
  chaptersApi: { list: vi.fn().mockResolvedValue([]), create: vi.fn() },
  volumesApi: { list: vi.fn().mockResolvedValue([]) },
  importApi: { preview: vi.fn(), commit: vi.fn() },
}));

// The global next-intl mock (setupTests.ts) returns raw keys, which would turn
// the matchers below into tautologies on key names. Resolving against the REAL
// en catalogs instead proves the rendered copy comes from the actual message
// trees — including the single-source rule that the failure banner text lives
// ONLY in importing.failedBanner (never duplicated into studio.json).
const messages: Record<string, unknown> = {
  studio: enStudio,
  importing: enImporting,
};

vi.mock("next-intl", () => ({
  useTranslations: (namespace: string) => (key: string, params?: Record<string, unknown>) => {
    let value: unknown = messages;
    for (const segment of `${namespace}.${key}`.split(".")) {
      if (value && typeof value === "object") {
        value = (value as Record<string, unknown>)[segment];
      }
    }
    let text = typeof value === "string" ? value : `${namespace}.${key}`;
    if (params) {
      for (const [name, replacement] of Object.entries(params)) {
        text = text.replace(`{${name}}`, String(replacement));
      }
    }
    return text;
  },
}));

function renderList() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SidebarChapterList novelId="novel-1" />
    </QueryClientProvider>,
  );
}

describe("SidebarChapterList import entry", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  it("shows an import action that opens the ImportModal", async () => {
    renderList();
    fireEvent.click(await screen.findByRole("button", { name: /import chapters/i }));
    await waitFor(() => expect(screen.getByText(/detected from frontmatter/i)).toBeInTheDocument());
  });

  it("renders the failure banner from the sessionStorage flag", async () => {
    sessionStorage.setItem("narrare:importFailed:novel-1", "1");
    renderList();
    expect(await screen.findByText(/chapters could not be imported/i)).toBeInTheDocument();
  });

  it("retry from the failure banner reopens the ImportModal", async () => {
    sessionStorage.setItem("narrare:importFailed:novel-1", "1");
    renderList();
    fireEvent.click(await screen.findByRole("button", { name: /retry import/i }));
    await waitFor(() => expect(screen.getByText(/detected from frontmatter/i)).toBeInTheDocument());
  });

  it("dismissing clears the banner and the sessionStorage flag", async () => {
    sessionStorage.setItem("narrare:importFailed:novel-1", "1");
    renderList();
    fireEvent.click(await screen.findByRole("button", { name: /dismiss/i }));
    await waitFor(() =>
      expect(screen.queryByText(/chapters could not be imported/i)).not.toBeInTheDocument(),
    );
    expect(sessionStorage.getItem("narrare:importFailed:novel-1")).toBeNull();
  });
});
