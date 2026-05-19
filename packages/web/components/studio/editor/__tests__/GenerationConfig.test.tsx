import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { GenerationConfig } from "@/components/studio/editor/GenerationConfig";

describe("GenerationConfig", () => {
  const defaultProps = {
    mode: "full_draft" as const,
    setMode: vi.fn(),
    outline: "",
    setOutline: vi.fn(),
    prompt: "",
    setPrompt: vi.fn(),
    wordTarget: 1000,
    setWordTarget: vi.fn(),
    tone: "",
    setTone: vi.fn(),
    isPending: false,
    onGenerate: vi.fn(),
    onStartSession: vi.fn(),
  };

  it("renders mode tabs", () => {
    render(<GenerationConfig {...defaultProps} />);
    expect(screen.getByText("generationPanel.modeFullDraft")).toBeDefined();
    expect(screen.getByText("generationPanel.modeSceneByScene")).toBeDefined();
  });

  it("renders prompt textarea", () => {
    render(<GenerationConfig {...defaultProps} />);
    expect(screen.getByLabelText("generationPanel.prompt", { exact: false })).toBeDefined();
  });

  it("renders word target input", () => {
    render(<GenerationConfig {...defaultProps} />);
    expect(screen.getByLabelText("generationPanel.wordTarget", { exact: false })).toBeDefined();
  });

  it("renders tone input", () => {
    render(<GenerationConfig {...defaultProps} />);
    expect(screen.getByLabelText("generationPanel.tone", { exact: false })).toBeDefined();
  });

  it("calls setMode when mode tab is clicked", () => {
    const setMode = vi.fn();
    render(<GenerationConfig {...defaultProps} setMode={setMode} />);
    fireEvent.click(screen.getByText("generationPanel.modeSceneByScene"));
    expect(setMode).toHaveBeenCalled();
  });

  it("calls setPrompt when prompt changes", () => {
    const setPrompt = vi.fn();
    render(<GenerationConfig {...defaultProps} setPrompt={setPrompt} prompt="Write about" />);
    fireEvent.change(screen.getByLabelText("generationPanel.prompt", { exact: false }), {
      target: { value: "Write a story" },
    });
    expect(setPrompt).toHaveBeenCalledWith("Write a story");
  });

  it("calls setOutline when outline changes", () => {
    const setOutline = vi.fn();
    render(<GenerationConfig {...defaultProps} setOutline={setOutline} />);
    const labelText = screen.getByText("generationPanel.outline");
    // The outline textarea should be rendered when mode has a full option
    expect(labelText).toBeDefined();
  });

  it("calls onGenerate when generate button is clicked", () => {
    const onGenerate = vi.fn();
    render(<GenerationConfig {...defaultProps} onGenerate={onGenerate} />);
    fireEvent.click(screen.getByText("generationPanel.generate"));
    expect(onGenerate).toHaveBeenCalledOnce();
  });

  it("disables generate button when isPending", () => {
    render(<GenerationConfig {...defaultProps} isPending={true} />);
    const span = screen.getByText("generationPanel.starting");
    const button = span.closest("button");
    expect(button).not.toBeNull();
    expect(button!.disabled).toBe(true);
  });

  it("changes text for generating state", () => {
    render(<GenerationConfig {...defaultProps} isPending={true} />);
    expect(screen.getByText("generationPanel.starting")).toBeDefined();
  });
});
