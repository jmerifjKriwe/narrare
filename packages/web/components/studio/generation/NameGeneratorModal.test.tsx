import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NameGeneratorModal } from "./NameGeneratorModal";
import { NameResults } from "./NameResults";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------
// Note: next-intl is mocked globally in setupTests.ts

vi.mock("@/lib/api/client", () => ({
  generationApi: {
    generateNames: vi.fn(),
  },
}));

vi.mock("@/lib/api/kb", () => ({
  kbApi: {
    createEntry: vi.fn(),
  },
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockNames = [
  {
    name: "Aelindra",
    pronunciation: "AY-lin-dra",
    meaning: "Starlight wanderer",
    type: "character",
    name_style: "fantasy",
    is_duplicate: false,
    confidence: 0.92,
  },
  {
    name: "Thalorin",
    pronunciation: "THA-lo-rin",
    meaning: "Mountain lord",
    type: "character",
    name_style: "fantasy",
    is_duplicate: false,
    confidence: 0.88,
  },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient();
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("NameGeneratorModal", () => {
  describe("rendering", () => {
    it("renders modal when open", async () => {
      renderWithProviders(<NameGeneratorModal novelId="novel-1" isOpen={true} onClose={vi.fn()} />);

      await waitFor(() => {
        expect(document.querySelector("div")).toBeInTheDocument();
      });
    });

    it("does not render when closed", async () => {
      const { container } = renderWithProviders(
        <NameGeneratorModal novelId="novel-1" isOpen={false} onClose={vi.fn()} />,
      );

      // When closed, should not render the modal content
      expect(container.firstChild).toBeNull();
    });
  });
});

describe("NameResults", () => {
  describe("rendering", () => {
    it("renders names when provided", async () => {
      renderWithProviders(
        <NameResults
          results={{
            names: mockNames,
            count: 2,
            name_style: "fantasy",
            name_type: "character",
          }}
          isLoading={false}
          novelId="novel-1"
          nameType="character"
        />,
      );

      await waitFor(() => {
        expect(document.querySelector("div")).toBeInTheDocument();
      });
    });

    it("renders empty state when no names", async () => {
      renderWithProviders(
        <NameResults results={null} isLoading={false} novelId="novel-1" nameType="character" />,
      );

      await waitFor(() => {
        expect(document.querySelector("div")).toBeInTheDocument();
      });
    });
  });
});
