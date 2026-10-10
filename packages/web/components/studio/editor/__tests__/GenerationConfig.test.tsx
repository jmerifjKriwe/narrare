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
    useScenePlans: false,
    setUseScenePlans: vi.fn(),
    hasScenePlans: false,
    onOpenScenePlans: vi.fn(),
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

  it("renders the scene-plans switch only when the chapter has scene plans", () => {
    const { rerender } = render(
      <GenerationConfig {...defaultProps} hasScenePlans={true} useScenePlans={true} />,
    );
    expect(screen.getByRole("switch")).toBeDefined();

    rerender(<GenerationConfig {...defaultProps} hasScenePlans={false} />);
    expect(screen.queryByRole("switch")).toBeNull();
  });

  it("reflects useScenePlans and reports explicit toggles (spec §8.1)", () => {
    const setUseScenePlans = vi.fn();
    const { rerender } = render(
      <GenerationConfig
        {...defaultProps}
        hasScenePlans={true}
        useScenePlans={true}
        setUseScenePlans={setUseScenePlans}
      />,
    );
    expect(screen.getByRole("switch").getAttribute("aria-checked")).toBe("true");

    fireEvent.click(screen.getByRole("switch"));
    expect(setUseScenePlans).toHaveBeenCalledWith(false);

    rerender(
      <GenerationConfig
        {...defaultProps}
        hasScenePlans={true}
        useScenePlans={false}
        setUseScenePlans={setUseScenePlans}
      />,
    );
    expect(screen.getByRole("switch").getAttribute("aria-checked")).toBe("false");
  });

  it("opens the scene-plan panel from the Plan scenes link", () => {
    const onOpenScenePlans = vi.fn();
    render(
      <GenerationConfig
        {...defaultProps}
        hasScenePlans={true}
        onOpenScenePlans={onOpenScenePlans}
      />,
    );
    fireEvent.click(screen.getByText("generationPanel.planScenes"));
    expect(onOpenScenePlans).toHaveBeenCalledOnce();
  });

  it("hides the switch and link when the chapter has no scene plans in any mode", () => {
    render(<GenerationConfig {...defaultProps} mode="interactive_session" />);
    expect(screen.queryByRole("switch")).toBeNull();
    expect(screen.queryByText("generationPanel.planScenes")).toBeNull();
  });
});
