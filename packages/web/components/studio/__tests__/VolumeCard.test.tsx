import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { VolumeCard, VolumeFormFields } from "@/components/studio/VolumeCard";
import type { Volume, VolumeStats } from "@/types";

// --- Mock data ---

const mockVolume: Volume = {
  id: "vol-1",
  novel_id: "novel-1",
  title: "Test Volume",
  subtitle: "A subtitle",
  description: "A description",
  word_count_target: 50000,
  position: 1,
  is_default: false,
  created_at: "2024-01-01T00:00:00Z",
};

const defaultVolume: Volume = {
  ...mockVolume,
  id: "vol-default",
  is_default: true,
};

const mockStats: VolumeStats = {
  chapter_count: 5,
  word_count: 12000,
  word_count_target: 50000,
  completion_percentage: 24,
};

const emptyStats: VolumeStats = {
  chapter_count: 0,
  word_count: 0,
  word_count_target: null,
  completion_percentage: null,
};

// --- VolumeCard tests ---

describe("VolumeCard", () => {
  describe("display mode", () => {
    it("renders volume title", () => {
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
          isFirst={false}
          isLast={false}
          isSaving={false}
        />,
      );
      expect(screen.getByText("Test Volume")).toBeDefined();
    });

    it("renders subtitle when present", () => {
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
          isFirst={false}
          isLast={false}
          isSaving={false}
        />,
      );
      expect(screen.getByText("A subtitle")).toBeDefined();
    });

    it("shows default badge for default volume", () => {
      render(
        <VolumeCard
          volume={defaultVolume}
          stats={mockStats}
          isEditing={false}
          onStartEdit={vi.fn()}
          onCancelEdit={vi.fn()}
          onSave={vi.fn()}
          onDelete={vi.fn()}
          onReorderUp={vi.fn()}
          onReorderDown={vi.fn()}
          isFirst={false}
          isLast={false}
          isSaving={false}
        />,
      );
      expect(screen.getByText("volumes.defaultBadge")).toBeDefined();
    });

    it("displays chapter count and word count from stats", () => {
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
          isFirst={false}
          isLast={false}
          isSaving={false}
        />,
      );
      expect(screen.getByText("volumes.chapterCount")).toBeDefined();
      expect(screen.getByText("volumes.wordCount")).toBeDefined();
      expect(screen.getByText("volumes.completion")).toBeDefined();
    });

    it("shows no-target text when completion_percentage is null", () => {
      render(
        <VolumeCard
          volume={mockVolume}
          stats={emptyStats}
          isEditing={false}
          onStartEdit={vi.fn()}
          onCancelEdit={vi.fn()}
          onSave={vi.fn()}
          onDelete={vi.fn()}
          onReorderUp={vi.fn()}
          onReorderDown={vi.fn()}
          isFirst={false}
          isLast={false}
          isSaving={false}
        />,
      );
      expect(screen.getByText("volumes.noTarget")).toBeDefined();
    });

    it("hides stats block when stats is undefined", () => {
      render(
        <VolumeCard
          volume={mockVolume}
          stats={undefined}
          isEditing={false}
          onStartEdit={vi.fn()}
          onCancelEdit={vi.fn()}
          onSave={vi.fn()}
          onDelete={vi.fn()}
          onReorderUp={vi.fn()}
          onReorderDown={vi.fn()}
          isFirst={false}
          isLast={false}
          isSaving={false}
        />,
      );
      expect(screen.queryByText("volumes.chapterCount")).toBeNull();
    });
  });

  describe("interactions", () => {
    it("calls onStartEdit when edit button is clicked", () => {
      const onStartEdit = vi.fn();
      render(
        <VolumeCard
          volume={mockVolume}
          stats={mockStats}
          isEditing={false}
          onStartEdit={onStartEdit}
          onCancelEdit={vi.fn()}
          onSave={vi.fn()}
          onDelete={vi.fn()}
          onReorderUp={vi.fn()}
          onReorderDown={vi.fn()}
          isFirst={false}
          isLast={false}
          isSaving={false}
        />,
      );
      const editBtn = screen.getByLabelText("volumes.editVolume");
      fireEvent.click(editBtn);
      expect(onStartEdit).toHaveBeenCalledOnce();
    });

    it("calls onReorderUp when up button is clicked", () => {
      const onReorderUp = vi.fn();
      render(
        <VolumeCard
          volume={mockVolume}
          stats={mockStats}
          isEditing={false}
          onStartEdit={vi.fn()}
          onCancelEdit={vi.fn()}
          onSave={vi.fn()}
          onDelete={vi.fn()}
          onReorderUp={onReorderUp}
          onReorderDown={vi.fn()}
          isFirst={false}
          isLast={false}
          isSaving={false}
        />,
      );
      const upBtn = screen.getByLabelText("volumes.reorderUp");
      fireEvent.click(upBtn);
      expect(onReorderUp).toHaveBeenCalledOnce();
    });

    it("calls onReorderDown when down button is clicked", () => {
      const onReorderDown = vi.fn();
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
          onReorderDown={onReorderDown}
          isFirst={false}
          isLast={false}
          isSaving={false}
        />,
      );
      const downBtn = screen.getByLabelText("volumes.reorderDown");
      fireEvent.click(downBtn);
      expect(onReorderDown).toHaveBeenCalledOnce();
    });

    it("disables reorder up for first volume", () => {
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
          isLast={false}
          isSaving={false}
        />,
      );
      const upBtn = screen.getByLabelText("volumes.reorderUp");
      expect((upBtn as HTMLButtonElement).disabled).toBe(true);
    });

    it("disables reorder down for last volume", () => {
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
          isFirst={false}
          isLast={true}
          isSaving={false}
        />,
      );
      const downBtn = screen.getByLabelText("volumes.reorderDown");
      expect((downBtn as HTMLButtonElement).disabled).toBe(true);
    });
  });

  describe("delete behavior", () => {
    beforeAll(() => {
      vi.spyOn(window, "confirm").mockReturnValue(true);
    });

    afterAll(() => {
      vi.restoreAllMocks();
    });

    it("calls onDelete for non-default volume after confirm", () => {
      const onDelete = vi.fn();
      render(
        <VolumeCard
          volume={mockVolume}
          stats={mockStats}
          isEditing={false}
          onStartEdit={vi.fn()}
          onCancelEdit={vi.fn()}
          onSave={vi.fn()}
          onDelete={onDelete}
          onReorderUp={vi.fn()}
          onReorderDown={vi.fn()}
          isFirst={false}
          isLast={false}
          isSaving={false}
        />,
      );
      const deleteBtn = screen.getByLabelText("volumes.deleteVolume");
      fireEvent.click(deleteBtn);
      expect(onDelete).toHaveBeenCalledWith("vol-1");
    });

    it("does not call onDelete for default volume", () => {
      const onDelete = vi.fn();
      render(
        <VolumeCard
          volume={defaultVolume}
          stats={mockStats}
          isEditing={false}
          onStartEdit={vi.fn()}
          onCancelEdit={vi.fn()}
          onSave={vi.fn()}
          onDelete={onDelete}
          onReorderUp={vi.fn()}
          onReorderDown={vi.fn()}
          isFirst={false}
          isLast={false}
          isSaving={false}
        />,
      );
      const deleteBtn = screen.getByLabelText("volumes.deleteVolume");
      fireEvent.click(deleteBtn);
      expect(onDelete).not.toHaveBeenCalled();
    });
  });
});

describe("VolumeFormFields", () => {
  const defaultProps = {
    title: "",
    subtitle: "",
    description: "",
    target: "",
    onTitleChange: vi.fn(),
    onSubtitleChange: vi.fn(),
    onDescriptionChange: vi.fn(),
    onTargetChange: vi.fn(),
    onSubmit: vi.fn(),
    onCancel: vi.fn(),
    submitLabel: "Save",
    isPending: false,
  };

  it("renders form fields", () => {
    render(<VolumeFormFields {...defaultProps} />);
    expect(screen.getByLabelText("volumes.titleLabel", { exact: false })).toBeDefined();
    expect(screen.getByLabelText("volumes.subtitleLabel", { exact: false })).toBeDefined();
    expect(screen.getByLabelText("volumes.descriptionLabel", { exact: false })).toBeDefined();
    expect(screen.getByLabelText("volumes.wordCountTargetLabel", { exact: false })).toBeDefined();
  });

  it("displays initial values", () => {
    render(
      <VolumeFormFields
        {...defaultProps}
        title="My Title"
        subtitle="Sub"
        description="Desc"
        target="75000"
      />,
    );
    expect(
      (screen.getByLabelText("volumes.titleLabel", { exact: false }) as HTMLInputElement).value,
    ).toBe("My Title");
    expect(
      (screen.getByLabelText("volumes.subtitleLabel", { exact: false }) as HTMLInputElement).value,
    ).toBe("Sub");
    expect(
      (screen.getByLabelText("volumes.descriptionLabel", { exact: false }) as HTMLTextAreaElement)
        .value,
    ).toBe("Desc");
    expect(
      (screen.getByLabelText("volumes.wordCountTargetLabel", { exact: false }) as HTMLInputElement)
        .value,
    ).toBe("75000");
  });

  it("calls onTitleChange when title input changes", () => {
    const onTitleChange = vi.fn();
    render(<VolumeFormFields {...defaultProps} onTitleChange={onTitleChange} />);
    fireEvent.change(screen.getByLabelText("volumes.titleLabel", { exact: false }), {
      target: { value: "New Title" },
    });
    expect(onTitleChange).toHaveBeenCalledWith("New Title");
  });

  it("calls onSubmit when submit button is clicked", () => {
    const onSubmit = vi.fn();
    render(<VolumeFormFields {...defaultProps} onSubmit={onSubmit} title="Valid Title" />);
    fireEvent.click(screen.getByText("Save"));
    expect(onSubmit).toHaveBeenCalledOnce();
  });

  it("disables submit button when title is empty", () => {
    render(<VolumeFormFields {...defaultProps} title="" />);
    expect((screen.getByText("Save") as HTMLButtonElement).disabled).toBe(true);
  });

  it("disables submit button when isPending is true", () => {
    render(<VolumeFormFields {...defaultProps} title="Title" isPending={true} />);
    // When isPending is true, the button shows a spinner icon instead of text
    const buttons = screen.getAllByRole("button");
    const submitBtn = buttons[buttons.length - 1] as HTMLButtonElement; // last button = submit
    expect(submitBtn.disabled).toBe(true);
  });

  it("calls onCancel when cancel button is clicked", () => {
    const onCancel = vi.fn();
    render(<VolumeFormFields {...defaultProps} onCancel={onCancel} />);
    fireEvent.click(screen.getByText("volumes.cancel"));
    expect(onCancel).toHaveBeenCalledOnce();
  });
});
