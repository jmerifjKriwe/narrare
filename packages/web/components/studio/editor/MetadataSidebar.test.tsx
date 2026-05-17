import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { createChapter, createChapterSummary } from "@/mocks/data";
import type { Chapter, ChapterSummary } from "@/types";
import { MetadataSidebar } from "./MetadataSidebar";

// Mock next-intl
vi.mock("next-intl", () => ({
  useTranslations: () => (key: string, params?: Record<string, unknown>) => {
    if (params) {
      return Object.entries(params).reduce((str, [k, v]) => str.replace(`{${k}}`, String(v)), key);
    }
    return key;
  },
  useLocale: () => "en",
}));

// ---------------------------------------------------------------------------
// Shared fixtures
// ---------------------------------------------------------------------------

const mockChapter: Chapter = createChapter({
  id: "ch-1",
  novel_id: "novel-1",
  title: "Test Chapter",
  content: "<p>Hello world</p>",
  word_count: 500,
  status: "draft",
  pov_character_id: "char-1",
  timeline_position: "Day 1",
  position: 0,
});

const mockChapters: ChapterSummary[] = [
  createChapterSummary({
    id: "ch-1",
    novel_id: "novel-1",
    title: "Ch 1",
    position: 0,
    word_count: 500,
    status: "draft",
  }),
  createChapterSummary({
    id: "ch-2",
    novel_id: "novel-1",
    title: "Ch 2",
    position: 1,
    word_count: 300,
    status: "reviewed",
  }),
  createChapterSummary({
    id: "ch-3",
    novel_id: "novel-1",
    title: "Ch 3",
    position: 2,
    word_count: 200,
    status: "final",
  }),
];

const defaultProps = {
  wordCount: 500,
  charCount: 2500,
  paragraphCount: 10,
  chapter: mockChapter as Chapter | null,
  chapters: mockChapters,
  sessionStartWordCount: 500,
};

// ---------------------------------------------------------------------------
// Rendering tests
// ---------------------------------------------------------------------------

describe("MetadataSidebar", () => {
  describe("rendering", () => {
    it("renders all four section headers", () => {
      render(<MetadataSidebar {...defaultProps} />);

      expect(screen.getByText("metadataSidebar.statistics")).toBeInTheDocument();
      expect(screen.getByText("metadataSidebar.session")).toBeInTheDocument();
      expect(screen.getByText("metadataSidebar.chapterInfo")).toBeInTheDocument();
      expect(screen.getByText("metadataSidebar.novelProgress")).toBeInTheDocument();
    });

    it("shows correct word count, character count, and paragraph count", () => {
      render(<MetadataSidebar {...defaultProps} />);

      // formatWordCount(500, "en") → "500"
      expect(screen.getByText("500")).toBeInTheDocument();
      // formatWordCount(2500, "en") → "2,500"
      expect(screen.getByText("2,500")).toBeInTheDocument();
      // String(paragraphCount) → "10"
      expect(screen.getByText("10")).toBeInTheDocument();
    });

    it("shows reading time computed as Math.ceil(wordCount / 250)", () => {
      // 500 words / 250 = 2 minutes
      render(<MetadataSidebar {...defaultProps} />);
      expect(screen.getByText("metadataSidebar.readingTimeValue")).toBeInTheDocument();
    });

    it("shows reading time of 1 minute for 250 words", () => {
      render(<MetadataSidebar {...defaultProps} wordCount={250} />);
      // Math.ceil(250/250) = 1
      expect(screen.getByText("metadataSidebar.readingTimeValue")).toBeInTheDocument();
    });

    it("shows reading time of 1 minute for 1 word (rounds up)", () => {
      render(<MetadataSidebar {...defaultProps} wordCount={1} />);
      // Math.ceil(1/250) = 1
      expect(screen.getByText("metadataSidebar.readingTimeValue")).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Session delta tests
  // -------------------------------------------------------------------------

  describe("session delta", () => {
    it("shows green text for positive delta", () => {
      render(<MetadataSidebar {...defaultProps} wordCount={550} sessionStartWordCount={500} />);

      const deltaEl = screen.getByText("metadataSidebar.sessionDelta");
      expect(deltaEl).toBeInTheDocument();
      expect(deltaEl.className).toContain("text-green-600");
    });

    it("shows red text for negative delta", () => {
      render(<MetadataSidebar {...defaultProps} wordCount={450} sessionStartWordCount={500} />);

      const deltaEl = screen.getByText("metadataSidebar.sessionDeltaNegative");
      expect(deltaEl).toBeInTheDocument();
      expect(deltaEl.className).toContain("text-red-600");
    });

    it("shows neutral text for zero delta", () => {
      render(<MetadataSidebar {...defaultProps} wordCount={500} sessionStartWordCount={500} />);

      // With zero delta, the key is "metadataSidebar.sessionDelta" but with muted styling
      const deltaEls = screen.getAllByText("metadataSidebar.sessionDelta");
      // Find the one with muted-foreground (the session delta, not the session start label)
      const mutedDelta = deltaEls.find((el) => el.className.includes("text-muted-foreground"));
      expect(mutedDelta).toBeInTheDocument();
    });

    it("shows session start word count", () => {
      render(<MetadataSidebar {...defaultProps} sessionStartWordCount={400} />);

      // formatWordCount(400, "en") → "400"
      expect(screen.getByText("metadataSidebar.sessionStart")).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Chapter info tests
  // -------------------------------------------------------------------------

  describe("chapter info", () => {
    it("shows status badge for draft", () => {
      render(<MetadataSidebar {...defaultProps} />);

      const badge = screen.getByText("draft");
      expect(badge).toBeInTheDocument();
      expect(badge.className).toContain("bg-yellow-100");
    });

    it("shows status badge for reviewed", () => {
      const chapter = createChapter({
        ...mockChapter,
        id: "ch-2",
        status: "reviewed",
      });
      render(<MetadataSidebar {...defaultProps} chapter={chapter} />);

      const badge = screen.getByText("reviewed");
      expect(badge).toBeInTheDocument();
      expect(badge.className).toContain("bg-blue-100");
    });

    it("shows status badge for final", () => {
      const chapter = createChapter({
        ...mockChapter,
        id: "ch-3",
        status: "final",
      });
      render(<MetadataSidebar {...defaultProps} chapter={chapter} />);

      const badge = screen.getByText("final");
      expect(badge).toBeInTheDocument();
      expect(badge.className).toContain("bg-green-100");
    });

    it("shows POV character id when set", () => {
      render(<MetadataSidebar {...defaultProps} />);

      expect(screen.getByText("char-1")).toBeInTheDocument();
    });

    it("shows not-set label when pov_character_id is empty", () => {
      const chapter = createChapter({ ...mockChapter, pov_character_id: "" });
      render(<MetadataSidebar {...defaultProps} chapter={chapter} />);

      expect(screen.getByText("metadataSidebar.noPov")).toBeInTheDocument();
    });

    it("shows timeline position when set", () => {
      render(<MetadataSidebar {...defaultProps} />);

      expect(screen.getByText("Day 1")).toBeInTheDocument();
    });

    it("shows not-set label when timeline_position is empty", () => {
      const chapter = createChapter({ ...mockChapter, timeline_position: "" });
      render(<MetadataSidebar {...defaultProps} chapter={chapter} />);

      expect(screen.getByText("metadataSidebar.noTimeline")).toBeInTheDocument();
    });

    it("shows chapter position key with current and total", () => {
      render(<MetadataSidebar {...defaultProps} />);

      // ch-1 is at index 0, so position = 1 of 3
      // The label AND value both render the same key via the mock,
      // so we expect two matching elements (label span + value span)
      const posTexts = screen.getAllByText("metadataSidebar.chapterPosition");
      expect(posTexts).toHaveLength(2);
    });

    it("shows select chapter message when chapter is null", () => {
      render(<MetadataSidebar {...defaultProps} chapter={null} />);

      expect(screen.getByText("editor.selectChapter")).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Novel progress tests
  // -------------------------------------------------------------------------

  describe("novel progress", () => {
    it("shows total words from all chapters", () => {
      render(<MetadataSidebar {...defaultProps} />);

      // Total = 500 + 300 + 200 = 1,000
      expect(screen.getByText("1,000")).toBeInTheDocument();
    });

    it("progress bar width reflects percentage", () => {
      const { container } = render(<MetadataSidebar {...defaultProps} />);

      // totalWords = 1000, WRITING_GOAL = 80000
      // progressPercent = Math.min(Math.round((1000/80000)*100), 100) = 1
      const bar = container.querySelector(".bg-primary") as HTMLElement;
      expect(bar).toBeInTheDocument();
      expect(bar.style.width).toBe("1%");
    });

    it("progress bar caps at 100%", () => {
      const hugeChapters = [
        createChapterSummary({ word_count: 50000 }),
        createChapterSummary({ word_count: 40000 }),
      ];
      const { container } = render(<MetadataSidebar {...defaultProps} chapters={hugeChapters} />);

      // Total = 90000, WRITING_GOAL = 80000 → percent = min(112, 100) = 100
      const bar = container.querySelector(".bg-primary") as HTMLElement;
      expect(bar).toBeInTheDocument();
      expect(bar.style.width).toBe("100%");
    });

    it("shows formatted progress label", () => {
      render(<MetadataSidebar {...defaultProps} />);

      expect(screen.getByText("metadataSidebar.progressLabel")).toBeInTheDocument();
    });
  });
});
