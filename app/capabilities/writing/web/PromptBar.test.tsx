// @vitest-environment jsdom
/**
 * The floating prompt bar (W4 Task 16) — the scene-centric draft's bar on
 * the shell's tokens: the neutral Stil trigger (INTERIM #878 — no style
 * presets exist), the inline input and the „Weiterschreiben" primary, the
 * three quick pills whose localized labels ride the prompt parameter (D5).
 * The bound mirrors the schema (1–2000 raw, no trim) with the app's
 * field-error family; the busy face is KACHEL 7's spinner + Stoppen, the
 * error face lives at the scene tail (the bar rests idle again).
 */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { applyLocale } from "@shell/lib/locale";
import { de, merged } from "@shell/lib/test/catalogs";

import { PromptBar } from "./PromptBar";
import { PROMPT_MAX_LENGTH, type Continuation } from "./workspace";

const INPUT_LABEL = de["writing.workspace.promptBar.inputLabel"];
const CONTINUE = de["writing.workspace.promptBar.continue"];

// The style trigger names its state, not a future wave (#979).
const STATUS_NOTE = {
  en: "Not available yet.",
  de: "Noch nicht verfügbar.",
  fr: "Pas encore disponible.",
} as const;

const FUTURE_PROMISE =
  /build-out|aufbau|wave|welle|vague|appear|erschein|appara|coming soon|kommt mit|arrive avec|future|becomes available|later/i;

describe("the style note speaks to the reader", () => {
  it("is status-only in every catalog, never a future promise", () => {
    for (const locale of ["en", "de", "fr"] as const) {
      const note = merged[locale]["writing.workspace.promptBar.styleNote"];
      expect(note).toBe(STATUS_NOTE[locale]);
      expect(note).not.toMatch(FUTURE_PROMISE);
    }
  });
});

function continuationOf(overrides: Partial<Continuation> = {}): Continuation {
  return {
    phase: "idle",
    text: "",
    errorCode: null,
    start: vi.fn(),
    dismiss: vi.fn(),
    retry: vi.fn(),
    ...overrides,
  };
}

function inputOf(): HTMLInputElement {
  return screen.getByRole("textbox", { name: INPUT_LABEL }) as HTMLInputElement;
}

beforeEach(() => {
  applyLocale("de");
});

afterEach(() => {
  cleanup();
});

describe("the idle face — the drafted bar", () => {
  it("renders the Stil trigger neutral, the input, the primary and the three pills", () => {
    render(<PromptBar continuation={continuationOf()} />);
    // The Stil trigger keeps its geometry and claims nothing (row 13).
    const stil = screen.getByRole("button", { name: /Stil:/ }) as HTMLButtonElement;
    expect(stil.disabled).toBe(true);
    expect(stil.textContent).toContain("—");
    expect(stil.getAttribute("title")).toBe(de["writing.workspace.promptBar.styleNote"]);
    // The input is a real labelled field with the drafted placeholder.
    expect(inputOf().getAttribute("placeholder")).toBe(de["writing.workspace.promptBar.placeholder"]);
    expect(screen.getByRole("button", { name: CONTINUE })).not.toBeNull();
    // The drafted three — the story-specific words are draft data, the
    // brief's generic copy ships (localized).
    for (const key of [
      "writing.workspace.promptBar.pillTension",
      "writing.workspace.promptBar.pillDialogue",
      "writing.workspace.promptBar.pillDetail",
    ] as const) {
      expect(screen.getByRole("button", { name: de[key] })).not.toBeNull();
    }
  });

  it("a quick pill sends its own label as the prompt — the round-trip", () => {
    const continuation = continuationOf();
    render(<PromptBar continuation={continuation} />);
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.promptBar.pillTension"] }));
    expect(continuation.start).toHaveBeenCalledWith("Spannungsspitze einbauen");
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.promptBar.pillDialogue"] }));
    expect(continuation.start).toHaveBeenCalledWith("Dialog vertiefen");
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.promptBar.pillDetail"] }));
    expect(continuation.start).toHaveBeenCalledWith("Details ausschmücken");
  });

  it("the input's instruction rides Enter and the primary alike", () => {
    const continuation = continuationOf();
    render(<PromptBar continuation={continuation} />);
    const input = inputOf();
    fireEvent.change(input, { target: { value: "Lass Mira am Ufer zögern." } });
    fireEvent.submit(input.closest("form") as HTMLFormElement);
    expect(continuation.start).toHaveBeenCalledWith("Lass Mira am Ufer zögern.");
    fireEvent.click(screen.getByRole("button", { name: CONTINUE }));
    expect(continuation.start).toHaveBeenCalledTimes(2);
  });

  it("an empty input is the bare continuation — no prompt at all", () => {
    const continuation = continuationOf();
    render(<PromptBar continuation={continuation} />);
    fireEvent.click(screen.getByRole("button", { name: CONTINUE }));
    expect(continuation.start).toHaveBeenCalledWith(undefined);
  });

  it("the bound mirrors the schema raw — whitespace passes, no trim", () => {
    const continuation = continuationOf();
    render(<PromptBar continuation={continuation} />);
    const input = inputOf();
    fireEvent.change(input, { target: { value: " " } });
    fireEvent.submit(input.closest("form") as HTMLFormElement);
    expect(continuation.start).toHaveBeenCalledWith(" ");
  });
});

describe("the bound refusal — the field-error family", () => {
  it("an over-long instruction names the refusal and never reaches the wire", () => {
    const continuation = continuationOf();
    render(<PromptBar continuation={continuation} />);
    const input = inputOf();
    fireEvent.change(input, { target: { value: "X".repeat(PROMPT_MAX_LENGTH + 1) } });
    const error = screen.getByRole("alert");
    expect(error.textContent).toContain("2000");
    expect(input.getAttribute("aria-invalid")).toBe("true");
    expect(input.getAttribute("aria-describedby")).toBe(error.id);
    fireEvent.submit(input.closest("form") as HTMLFormElement);
    fireEvent.click(screen.getByRole("button", { name: CONTINUE }));
    expect(continuation.start).not.toHaveBeenCalled();
  });

  it("the refusal clears when the instruction is back within the bound", () => {
    const continuation = continuationOf();
    render(<PromptBar continuation={continuation} />);
    const input = inputOf();
    fireEvent.change(input, { target: { value: "X".repeat(PROMPT_MAX_LENGTH + 1) } });
    expect(screen.getByRole("alert")).not.toBeNull();
    fireEvent.change(input, { target: { value: "X".repeat(PROMPT_MAX_LENGTH) } });
    expect(screen.queryByRole("alert")).toBeNull();
    expect(input.getAttribute("aria-invalid")).toBe("false");
    fireEvent.submit(input.closest("form") as HTMLFormElement);
    expect(continuation.start).toHaveBeenCalledWith("X".repeat(PROMPT_MAX_LENGTH));
  });

  it("a pill sends even while the input stands over-long — its own ask, its own bound", () => {
    const continuation = continuationOf();
    render(<PromptBar continuation={continuation} />);
    fireEvent.change(inputOf(), { target: { value: "X".repeat(PROMPT_MAX_LENGTH + 1) } });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.promptBar.pillTension"] }));
    expect(continuation.start).toHaveBeenCalledWith("Spannungsspitze einbauen");
  });
});

describe("the busy face — KACHEL 7", () => {
  it("streams with the spinner label and Stoppen; the input rests", () => {
    const continuation = continuationOf({ phase: "streaming", text: "Der Nebel hob sich " });
    render(<PromptBar continuation={continuation} />);
    expect(screen.getByText(de["writing.workspace.promptBar.busy"])).not.toBeNull();
    expect(screen.queryByRole("textbox", { name: INPUT_LABEL })).toBeNull();
    expect(screen.queryByRole("button", { name: CONTINUE })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.promptBar.stop"] }));
    expect(continuation.dismiss).toHaveBeenCalled();
  });

  it("the error face rests the bar idle again — the failure lives at the tail", () => {
    const continuation = continuationOf({ phase: "error", errorCode: "network" });
    render(<PromptBar continuation={continuation} />);
    expect(inputOf()).not.toBeNull();
    expect(screen.queryByText(de["writing.workspace.promptBar.busy"])).toBeNull();
  });
});

describe("the localized faces", () => {
  it("the pills speak the active catalog — en and fr ride the same keys", () => {
    for (const locale of ["en", "fr"] as const) {
      applyLocale(locale);
      const catalog = merged[locale];
      const continuation = continuationOf();
      const { unmount } = render(<PromptBar continuation={continuation} />);
      fireEvent.click(
        screen.getByRole("button", { name: catalog["writing.workspace.promptBar.pillTension"] }),
      );
      expect(continuation.start).toHaveBeenCalledWith(catalog["writing.workspace.promptBar.pillTension"]);
      unmount();
    }
  });
});
