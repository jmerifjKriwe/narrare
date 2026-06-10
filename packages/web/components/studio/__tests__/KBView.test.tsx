/**
 * KB Browser tests — WorldBuilding component with sub-components.
 *
 * Tests:
 * 1. KB browser renders entity type tabs
 * 2. Entry card renders name, type, status
 * 3. Create form appears on "New Entry" click
 * 4. Search triggers on input
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WorldBuilding } from "@/components/studio/WorldBuilding";

// --- Test wrapper with QueryClient ---

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = createTestQueryClient();
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

// --- Tests ---

describe("KBView (WorldBuilding)", () => {
  const novelId = "novel-1";

  describe("entity type tabs", () => {
    it("renders the KB title header", async () => {
      renderWithQueryClient(<WorldBuilding novelId={novelId} />);
      // The category sidebar header uses t("kb.title") which in test returns the key
      expect(await screen.findByText("kb.title")).toBeDefined();
    });

    it("renders all 6 entity type tabs plus All", async () => {
      renderWithQueryClient(<WorldBuilding novelId={novelId} />);

      // Wait for data to load
      await waitFor(() => {
        expect(screen.getByText("kb.allTypes")).toBeDefined();
      });

      // Entity type labels use t("kb.characters") etc.
      expect(screen.getByText("kb.characters")).toBeDefined();
      expect(screen.getByText("kb.locations")).toBeDefined();
      expect(screen.getByText("kb.factions")).toBeDefined();
      expect(screen.getByText("kb.objects")).toBeDefined();
      expect(screen.getByText("kb.systems")).toBeDefined();
      expect(screen.getByText("kb.timelines")).toBeDefined();
    });

    it("renders count badges for entity types", async () => {
      renderWithQueryClient(<WorldBuilding novelId={novelId} />);

      // After data loads, the character count (2 mock entries) should show
      await waitFor(() => {
        const badges = screen.getAllByText("2");
        expect(badges.length).toBeGreaterThanOrEqual(1);
      });
    });
  });

  describe("entry list", () => {
    it("renders entry cards with name and status", async () => {
      renderWithQueryClient(<WorldBuilding novelId={novelId} />);

      // Wait for entries to load
      await waitFor(() => {
        expect(screen.getByText("Anna Schmidt")).toBeDefined();
      });

      // Status badge should be rendered (multiple canon entries)
      expect(screen.getAllByText("kb.status.canon").length).toBeGreaterThanOrEqual(1);
    });

    it("renders multiple entries from different types", async () => {
      renderWithQueryClient(<WorldBuilding novelId={novelId} />);

      await waitFor(() => {
        expect(screen.getByText("Anna Schmidt")).toBeDefined();
      });

      // "All" type is active by default, so all entries show
      expect(screen.getByText("The Old Archive")).toBeDefined();
      expect(screen.getByText("The Encrypted Diary")).toBeDefined();
    });
  });

  describe("create new entry", () => {
    it("shows create form when New Entry is clicked", async () => {
      renderWithQueryClient(<WorldBuilding novelId={novelId} />);

      // Wait for data to load
      await waitFor(() => {
        expect(screen.getByText("kb.newEntry")).toBeDefined();
      });

      // Click the "New Entry" button
      fireEvent.click(screen.getByText("kb.newEntry"));

      // Create form should appear
      await waitFor(() => {
        expect(screen.getByText("kb.selectType")).toBeDefined();
      });
    });

    it("create form has entity type selector, name input, and body textarea", async () => {
      renderWithQueryClient(<WorldBuilding novelId={novelId} />);

      await waitFor(() => {
        expect(screen.getByText("kb.newEntry")).toBeDefined();
      });

      fireEvent.click(screen.getByText("kb.newEntry"));

      await waitFor(() => {
        expect(screen.getByLabelText("kb.selectType")).toBeDefined();
        expect(screen.getByPlaceholderText("kb.namePlaceholder")).toBeDefined();
        expect(screen.getByPlaceholderText("kb.bodyPlaceholder")).toBeDefined();
      });
    });
  });

  describe("search", () => {
    it("renders search input in the entry list", async () => {
      renderWithQueryClient(<WorldBuilding novelId={novelId} />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText("kb.search")).toBeDefined();
      });
    });

    it("accepts input in the search field", async () => {
      renderWithQueryClient(<WorldBuilding novelId={novelId} />);

      const searchInput = await screen.findByPlaceholderText("kb.search");
      fireEvent.change(searchInput, { target: { value: "Anna" } });

      expect((searchInput as HTMLInputElement).value).toBe("Anna");
    });
  });

  describe("empty state", () => {
    it("shows select entry message when no entry is selected", async () => {
      renderWithQueryClient(<WorldBuilding novelId={novelId} />);

      await waitFor(() => {
        expect(screen.getByText("kb.selectEntry")).toBeDefined();
      });
    });
  });
});
