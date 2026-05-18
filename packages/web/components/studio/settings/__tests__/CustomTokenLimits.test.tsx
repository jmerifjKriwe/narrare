import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CustomTokenLimits } from "@/components/studio/settings/CustomTokenLimits";
import type { TokenLimitOverride } from "@/types";

const noOverrides: Record<string, TokenLimitOverride> = {};

const sampleOverrides: Record<string, TokenLimitOverride> = {
  writing: { max_tokens: 4000, temperature: 0.8 },
  analysis: { max_tokens: 8000, temperature: 0.3 },
};

describe("CustomTokenLimits", () => {
  it("renders all 7 categories", () => {
    render(<CustomTokenLimits overrides={noOverrides} onChange={vi.fn()} />);

    // Each category renders a label via the translation key pattern
    const categoryKeys = [
      "settings.ai.categories.writing",
      "settings.ai.categories.analysis",
      "settings.ai.categories.knowledgeBase",
      "settings.ai.categories.planning",
      "settings.ai.categories.extraction",
      "settings.ai.categories.chat",
      "settings.ai.categories.research",
    ];
    for (const key of categoryKeys) {
      expect(screen.getByText(key)).toBeDefined();
    }
  });

  it("renders max_tokens and temperature labels for each category", () => {
    render(<CustomTokenLimits overrides={noOverrides} onChange={vi.fn()} />);
    // There are 7 categories, each with two labels
    const maxLabels = screen.getAllByText("settings.ai.tokenLimits.maxTokens");
    const tempLabels = screen.getAllByText("settings.ai.tokenLimits.temperature");
    expect(maxLabels).toHaveLength(7);
    expect(tempLabels).toHaveLength(7);
  });

  it("displays default values when no overrides provided", () => {
    render(<CustomTokenLimits overrides={noOverrides} onChange={vi.fn()} />);

    // The first max_tokens input should default to the balanced default (2000)
    const maxInputs = screen.getAllByLabelText("settings.ai.tokenLimits.maxTokens");
    expect((maxInputs[0] as HTMLInputElement).value).toBe("2000");

    const tempInputs = screen.getAllByLabelText("settings.ai.tokenLimits.temperature");
    expect((tempInputs[0] as HTMLInputElement).value).toBe("0.7");
  });

  it("displays provided override values", () => {
    render(<CustomTokenLimits overrides={sampleOverrides} onChange={vi.fn()} />);

    const maxInputs = screen.getAllByLabelText("settings.ai.tokenLimits.maxTokens");
    // First category is "writing" → should have 4000
    expect((maxInputs[0] as HTMLInputElement).value).toBe("4000");

    // Analysis is the second category, so index 1
    expect((maxInputs[1] as HTMLInputElement).value).toBe("8000");
  });

  it("calls onChange when max_tokens is updated", () => {
    const onChange = vi.fn();
    render(<CustomTokenLimits overrides={noOverrides} onChange={onChange} />);

    const maxInputs = screen.getAllByLabelText("settings.ai.tokenLimits.maxTokens");
    fireEvent.change(maxInputs[0], { target: { value: "3000" } });

    // onChange should be called with the writing category's new override
    expect(onChange).toHaveBeenCalledWith({
      writing: { max_tokens: 3000, temperature: 0.7 },
    });
  });

  it("calls onChange when temperature is updated", () => {
    const onChange = vi.fn();
    render(<CustomTokenLimits overrides={noOverrides} onChange={onChange} />);

    const tempInputs = screen.getAllByLabelText("settings.ai.tokenLimits.temperature");
    fireEvent.change(tempInputs[0], { target: { value: "1.5" } });

    expect(onChange).toHaveBeenCalledWith({
      writing: { max_tokens: 2000, temperature: 1.5 },
    });
  });

  it("does not call onChange when max_tokens < 1", () => {
    const onChange = vi.fn();
    render(<CustomTokenLimits overrides={noOverrides} onChange={onChange} />);

    const maxInputs = screen.getAllByLabelText("settings.ai.tokenLimits.maxTokens");
    fireEvent.change(maxInputs[0], { target: { value: "0" } });

    expect(onChange).not.toHaveBeenCalled();
  });

  it("does not call onChange when temperature < 0", () => {
    const onChange = vi.fn();
    render(<CustomTokenLimits overrides={noOverrides} onChange={onChange} />);

    const tempInputs = screen.getAllByLabelText("settings.ai.tokenLimits.temperature");
    fireEvent.change(tempInputs[0], { target: { value: "-1" } });

    expect(onChange).not.toHaveBeenCalled();
  });

  it("does not call onChange when temperature > 2", () => {
    const onChange = vi.fn();
    render(<CustomTokenLimits overrides={noOverrides} onChange={onChange} />);

    const tempInputs = screen.getAllByLabelText("settings.ai.tokenLimits.temperature");
    fireEvent.change(tempInputs[0], { target: { value: "2.5" } });

    expect(onChange).not.toHaveBeenCalled();
  });

  it("does not call onChange for NaN input", () => {
    const onChange = vi.fn();
    render(<CustomTokenLimits overrides={noOverrides} onChange={onChange} />);

    const maxInputs = screen.getAllByLabelText("settings.ai.tokenLimits.maxTokens");
    fireEvent.change(maxInputs[0], { target: { value: "abc" } });

    expect(onChange).not.toHaveBeenCalled();
  });

  it("shows high-token warning when max_tokens > 128000", () => {
    const highOverrides: Record<string, TokenLimitOverride> = {
      writing: { max_tokens: 130000, temperature: 0.7 },
    };
    render(<CustomTokenLimits overrides={highOverrides} onChange={vi.fn()} />);

    expect(screen.getByText("settings.ai.tokenLimits.maxTokensWarning")).toBeDefined();
  });

  it("does not show high-token warning when max_tokens <= 128000", () => {
    render(<CustomTokenLimits overrides={noOverrides} onChange={vi.fn()} />);

    expect(screen.queryByText("settings.ai.tokenLimits.maxTokensWarning")).toBeNull();
  });
});
