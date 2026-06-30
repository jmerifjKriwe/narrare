/**
 * VoiceCheckTrigger tests — on-demand "Check Voice" run button (WRITE-010).
 *
 * Mirrors CharacterVoiceTrigger.test.tsx, adapted to the on-demand design:
 * character-voice's trigger is a store-coupled panel toggle (aria-pressed);
 * voice-check's trigger is a props-driven action button that RUNS the analysis
 * (aria-busy while loading, disabled-while-loading). Page/store wiring is 4c,
 * so this trigger is controlled via props (onClick / disabled / isLoading).
 *
 * next-intl is globally mocked in setupTests.ts (returns keys directly), so
 * assertions compare against i18n keys (e.g. "voiceCheck.trigger").
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { VoiceCheckTrigger } from "@/components/studio/analysis/VoiceCheckTrigger";

describe("VoiceCheckTrigger", () => {
  it("renders trigger button with label", () => {
    render(<VoiceCheckTrigger onClick={vi.fn()} />);

    expect(screen.getByText("voiceCheck.trigger")).toBeDefined();
  });

  it("renders with aria-label from triggerAriaLabel", () => {
    render(<VoiceCheckTrigger onClick={vi.fn()} />);

    expect(screen.getByLabelText("voiceCheck.triggerAriaLabel")).toBeDefined();
  });

  it("uses triggerTooltip as the title attribute", () => {
    render(<VoiceCheckTrigger onClick={vi.fn()} />);

    const button = screen.getByLabelText("voiceCheck.triggerAriaLabel");
    expect(button.getAttribute("title")).toBe("voiceCheck.triggerTooltip");
  });

  it("calls onClick when clicked", () => {
    const onClick = vi.fn();
    render(<VoiceCheckTrigger onClick={onClick} />);

    fireEvent.click(screen.getByText("voiceCheck.trigger"));

    expect(onClick).toHaveBeenCalledOnce();
  });

  it("is enabled by default", () => {
    render(<VoiceCheckTrigger onClick={vi.fn()} />);

    const button = screen.getByText("voiceCheck.trigger").closest("button")!;
    expect(button.disabled).toBe(false);
  });

  it("is disabled when disabled=true", () => {
    render(<VoiceCheckTrigger onClick={vi.fn()} disabled />);

    const button = screen.getByText("voiceCheck.trigger").closest("button")!;
    expect(button.disabled).toBe(true);
  });

  it("is disabled while loading (disabled-while-loading)", () => {
    render(<VoiceCheckTrigger onClick={vi.fn()} isLoading />);

    const button = screen.getByText("voiceCheck.trigger").closest("button")!;
    expect(button.disabled).toBe(true);
  });

  it("exposes aria-busy=true while loading", () => {
    render(<VoiceCheckTrigger onClick={vi.fn()} isLoading />);

    const button = screen.getByText("voiceCheck.trigger").closest("button")!;
    expect(button.getAttribute("aria-busy")).toBe("true");
  });

  it("does not call onClick when disabled", () => {
    const onClick = vi.fn();
    render(<VoiceCheckTrigger onClick={onClick} disabled />);

    const button = screen.getByText("voiceCheck.trigger").closest("button")!;
    fireEvent.click(button);

    expect(onClick).not.toHaveBeenCalled();
  });
});
