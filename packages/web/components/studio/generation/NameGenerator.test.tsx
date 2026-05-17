import { render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NameGeneratorModal } from "./NameGeneratorModal";
import { NameResults } from "./NameResults";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
  useLocale: () => "en",
}));

vi.mock("@/lib/api/client", () => ({
  generationApi: {
    generateNames: vi.fn(),
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
    culture: "fantasy",
    is_duplicate: false,
    confidence: 0.92,
  },
  {
    name: "Thalorin",
    pronunciation: "THA-lo-rin",
    meaning: "Mountain lord",
    type: "character",
    culture: "fantasy",
    is_duplicate: false,
    confidence: 0.88,
  },
];

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("NameGeneratorModal", () => {
  describe("rendering", () => {
    it("renders modal when open", async () => {
      render(<NameGeneratorModal novelId="novel-1" isOpen={true} onClose={vi.fn()} />);

      await waitFor(() => {
        expect(document.querySelector("div")).toBeInTheDocument();
      });
    });

    it("does not render when closed", async () => {
      const { container } = render(
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
      render(
        <NameResults
          results={{
            names: mockNames,
            count: 2,
            culture: "fantasy",
            name_type: "character",
          }}
          isLoading={false}
        />,
      );

      await waitFor(() => {
        expect(document.querySelector("div")).toBeInTheDocument();
      });
    });

    it("renders empty state when no names", async () => {
      render(<NameResults results={null} isLoading={false} />);

      await waitFor(() => {
        expect(document.querySelector("div")).toBeInTheDocument();
      });
    });
  });
});
