/**
 * GenerationInputFields tests — Keyboard shortcuts for generation input fields.
 *
 * Tests the Ctrl+Enter / Cmd+Enter handler on prompt and outline textareas:
 * 1. Ctrl+Enter triggers onGenerate
 * 2. Cmd+Enter (Mac) triggers onGenerate
 * 3. Plain Enter does NOT trigger onGenerate
 * 4. Works on both prompt and outline textareas
 * 5. Does not crash when onGenerate is undefined
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { GenerationInputFields } from "../GenerationInputFields";

describe("GenerationInputFields", () => {
  const defaultProps = {
    mode: "full_draft" as const,
    outline: "",
    setOutline: vi.fn(),
    prompt: "",
    setPrompt: vi.fn(),
    wordTarget: 1000,
    setWordTarget: vi.fn(),
    tone: "balanced",
    setTone: vi.fn(),
  };

  describe("keyboard shortcuts", () => {
    it("calls onGenerate on Ctrl+Enter in prompt textarea", () => {
      const onGenerate = vi.fn();
      render(<GenerationInputFields {...defaultProps} onGenerate={onGenerate} />);

      const textarea = screen.getByLabelText("generationPanel.prompt", { exact: false });
      fireEvent.keyDown(textarea, { key: "Enter", ctrlKey: true });

      expect(onGenerate).toHaveBeenCalledTimes(1);
    });

    it("calls onGenerate on Ctrl+Enter in outline textarea", () => {
      const onGenerate = vi.fn();
      render(<GenerationInputFields {...defaultProps} onGenerate={onGenerate} />);

      const textarea = screen.getByLabelText("generationPanel.outline", { exact: false });
      fireEvent.keyDown(textarea, { key: "Enter", ctrlKey: true });

      expect(onGenerate).toHaveBeenCalledTimes(1);
    });

    it("calls onGenerate on Cmd+Enter (Mac)", () => {
      const onGenerate = vi.fn();
      render(<GenerationInputFields {...defaultProps} onGenerate={onGenerate} />);

      const textarea = screen.getByLabelText("generationPanel.prompt", { exact: false });
      fireEvent.keyDown(textarea, { key: "Enter", metaKey: true });

      expect(onGenerate).toHaveBeenCalledTimes(1);
    });

    it("does NOT call onGenerate on plain Enter", () => {
      const onGenerate = vi.fn();
      render(<GenerationInputFields {...defaultProps} onGenerate={onGenerate} />);

      const textarea = screen.getByLabelText("generationPanel.prompt", { exact: false });
      fireEvent.keyDown(textarea, { key: "Enter" });

      expect(onGenerate).not.toHaveBeenCalled();
    });

    it("prevents default on Ctrl+Enter (does not insert newline)", () => {
      const onGenerate = vi.fn();
      render(<GenerationInputFields {...defaultProps} onGenerate={onGenerate} />);

      const textarea = screen.getByLabelText("generationPanel.prompt", { exact: false });
      const prevented = fireEvent.keyDown(textarea, { key: "Enter", ctrlKey: true });

      // The handler calls e.preventDefault()
      expect(prevented).toBe(false);
    });

    it("does not crash when onGenerate is undefined", () => {
      render(<GenerationInputFields {...defaultProps} />);

      const textarea = screen.getByLabelText("generationPanel.prompt", { exact: false });
      expect(() => {
        fireEvent.keyDown(textarea, { key: "Enter", ctrlKey: true });
      }).not.toThrow();
    });
  });
});
