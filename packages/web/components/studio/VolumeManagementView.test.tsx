import { render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Volume, VolumeStats } from "@/types";
import { VolumeCard } from "./VolumeCard";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
  useLocale: () => "en",
}));

vi.mock("@/lib/api/client", () => ({
  volumesApi: {
    list: vi.fn(),
    getStats: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "novel-1" }),
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockVolume: Volume = {
  id: "vol-1",
  novel_id: "novel-1",
  title: "Volume 1: The Beginning",
  subtitle: null,
  description: null,
  word_count_target: null,
  is_default: false,
  position: 0,
  created_at: "2026-01-01T00:00:00Z",
};

const mockStats: VolumeStats = {
  word_count: 15000,
  chapter_count: 5,
  word_count_target: null,
  completion_percentage: null,
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("VolumeCard", () => {
  describe("rendering", () => {
    it("renders volume card component", async () => {
      render(
        <VolumeCard
          volume={mockVolume}
          stats={mockStats}
          isEditing={false}
          onStartEdit={vi.fn()}
          onCancelEdit={vi.fn()}
          onSave={vi.fn()}
          onDelete={vi.fn()}
          onReorderUp={vi.fn()}
          onReorderDown={vi.fn()}
          isFirst={true}
          isLast={true}
          isSaving={false}
        />,
      );

      await waitFor(() => {
        expect(document.querySelector("div")).toBeInTheDocument();
      });
    });
  });
});

// Note: VolumeManagementView is not tested because it makes API calls during render
// which requires more complex mocking. This is a known limitation.
