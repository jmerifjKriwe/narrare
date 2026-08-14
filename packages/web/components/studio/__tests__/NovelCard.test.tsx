/**
 * NovelCard tests — presentational standalone-novel card
 * (Spec 1, Slice 4, Task 4.5).
 *
 * Extracted from the inline markup that used to live in NovelCardGrid so the
 * same card can sit in the mixed DashboardLibrary grid. Behaviour is
 * unchanged: title/author/genre render, the card links to /novel/[id], and
 * the edit / delete IconButtons fire their callbacks.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NovelCard } from "@/components/studio/NovelCard";
import type { NovelSummary } from "@/types";

const novel: NovelSummary = {
  id: "n1",
  title: "My Novel",
  author: "Jane Doe",
  genre: "Fantasy",
  writing_language: "en",
  is_demo: false,
  updated_at: "2024-01-01",
  series_id: null,
};

describe("NovelCard", () => {
  it("renders the title, author and genre", () => {
    render(
      <NovelCard
        novel={novel}
        formatDate={(d) => d}
        onDelete={vi.fn()}
        onEdit={vi.fn()}
        onExport={vi.fn()}
        isDeleting={false}
      />,
    );
    expect(screen.getByText("My Novel")).toBeDefined();
    expect(screen.getByText("Jane Doe")).toBeDefined();
    expect(screen.getByText("Fantasy")).toBeDefined();
  });

  it("links to /novel/[id]", () => {
    render(
      <NovelCard
        novel={novel}
        formatDate={(d) => d}
        onDelete={vi.fn()}
        onEdit={vi.fn()}
        onExport={vi.fn()}
        isDeleting={false}
      />,
    );
    expect(screen.getByRole("link")).toHaveAttribute("href", "/novel/n1");
  });

  it("calls onEdit when the edit button is clicked", () => {
    const onEdit = vi.fn();
    render(
      <NovelCard
        novel={novel}
        formatDate={(d) => d}
        onDelete={vi.fn()}
        onEdit={onEdit}
        onExport={vi.fn()}
        isDeleting={false}
      />,
    );
    fireEvent.click(screen.getByTestId("edit-novel-btn"));
    expect(onEdit).toHaveBeenCalledWith("n1");
  });

  it("calls onDelete with id and title when the delete button is clicked", () => {
    const onDelete = vi.fn();
    render(
      <NovelCard
        novel={novel}
        formatDate={(d) => d}
        onDelete={onDelete}
        onEdit={vi.fn()}
        onExport={vi.fn()}
        isDeleting={false}
      />,
    );
    fireEvent.click(screen.getByTestId("delete-novel-btn"));
    expect(onDelete).toHaveBeenCalledWith("n1", "My Novel");
  });

  it("calls onExport when the export button is clicked (IO-001)", () => {
    const onExport = vi.fn();
    render(
      <NovelCard
        novel={novel}
        formatDate={(d) => d}
        onDelete={vi.fn()}
        onEdit={vi.fn()}
        onExport={onExport}
        isDeleting={false}
      />,
    );
    fireEvent.click(screen.getByTestId("export-novel-btn"));
    expect(onExport).toHaveBeenCalledWith("n1");
  });
});
