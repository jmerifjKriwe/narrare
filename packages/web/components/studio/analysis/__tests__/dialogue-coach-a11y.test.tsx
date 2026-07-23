/**
 * axe-core a11y tests for the Dialogue Coach surface (ADR-069 §24 + §28; Task 12).
 *
 * Two complementary layers:
 *  1. Leaf components rendered directly with props — deterministic, no MSW —
 *     so the a11y of each building block (mode selector, issue list + cards +
 *     alternatives, empty state) is asserted in isolation.
 *  2. The {@link DialogueCoachPanel} composite driven through its SSE lifecycle
 *     (MSW) so the full panel markup is scanned per state (idle / analyze /
 *     improve / error).
 *
 * web-design-guidelines gate (what axe must keep clean here):
 *  - keyboard operability: every interactive element is a real `<button>`
 *    (axe `button-name`, `interactive-role`).
 *  - focus visibility: `focus-visible:ring-*` present on actionable elements.
 *  - ARIA: the mode group is a `<fieldset>`/`<legend>` with `aria-pressed`
 *    toggles; results live in `aria-live` regions.
 *  - colour-not-alone: severity badges render TEXT + a variant class, never a
 *    colour-only swatch (verified structurally in the edge-case block).
 *
 * The two page-level axe rules (`color-contrast`, `region`) are disabled in
 * the shared {@link runAxe} runner — see `lib/test/axe.ts` for the rationale.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { Editor } from "@tiptap/react";
import { HttpResponse, http } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DialogueAlternativeCard } from "@/components/studio/analysis/_components/DialogueAlternativeCard";
import { DialogueIssueCard } from "@/components/studio/analysis/_components/DialogueIssueCard";
import { DialogueIssueList } from "@/components/studio/analysis/_components/DialogueIssueList";
import { DialogueModeSelector } from "@/components/studio/analysis/_components/DialogueModeSelector";
import { DialogueCoachPanel } from "@/components/studio/analysis/DialogueCoachPanel";
import { runAxe } from "@/lib/test/axe";
import { server } from "@/mocks/server";
import type { DialogueAlternative, DialogueIssue } from "@/types";

/** Minimal TipTap Editor stand-in (mirrors DialogueCoachPanel.test.tsx). */
const fakeEditor = {
  getHTML: () => "<p>I am sad.</p>",
  state: { doc: { textBetween: () => "I am sad." } },
  chain: () => ({ focus: () => ({ setContent: vi.fn(), run: () => {} }) }),
} as unknown as Editor;

const ISSUE_ANALYZE: DialogueIssue = {
  issue_type: "on-the-nose",
  speaker: "Alice",
  original_quote: '"I am sad."',
  diagnosis: "Telling the emotion rather than showing it.",
  severity: "medium",
  alternatives: null,
};

const ISSUE_IMPROVE: DialogueIssue = {
  ...ISSUE_ANALYZE,
  alternatives: [
    { rewrite: '"Her shoulders slumped."', explanation: "Show the emotion physically." },
  ],
};

const ALT: DialogueAlternative = {
  rewrite: '"Her shoulders slumped."',
  explanation: "Show the emotion physically.",
};

afterEach(() => server.resetHandlers());

// ---------------------------------------------------------------------------
// Layer 1 — leaf components in isolation (deterministic, no MSW).
// ---------------------------------------------------------------------------

describe("DialogueModeSelector a11y", () => {
  it("renders a labelled fieldset of aria-pressed toggles with no violations", async () => {
    const { container } = render(
      <DialogueModeSelector mode="analyze" onSelect={vi.fn()} disabled={false} />,
    );
    // Structural a11y (colour-not-alone applies to buttons, but here we assert
    // the group semantics that axe also relies on).
    expect(container.querySelector("fieldset")).toBeInTheDocument();
    expect(container.querySelector("legend")).toBeInTheDocument();
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(2);
    for (const btn of buttons) {
      expect(btn).toHaveAttribute("aria-pressed");
    }
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("stays accessible when disabled", async () => {
    const { container } = render(
      <DialogueModeSelector mode="improve" onSelect={vi.fn()} disabled={true} />,
    );
    expect(await runAxe(container)).toHaveNoViolations();
  });
});

describe("DialogueIssueCard a11y", () => {
  it("analyze card (no alternatives): blockquote + severity badge, no violations", async () => {
    const { container } = render(
      <DialogueIssueCard issue={ISSUE_ANALYZE} editor={fakeEditor} onApplied={vi.fn()} />,
    );
    // Colour-not-alone: the severity is conveyed by text, not just colour.
    expect(container.querySelector("article")).toBeInTheDocument();
    expect(container.querySelector("blockquote")).toBeInTheDocument();
    expect(screen.getByText("dialogueCoach.severity.medium")).toBeInTheDocument();
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("improve card (with alternatives): before/after + Apply, no violations", async () => {
    const { container } = render(
      <DialogueIssueCard issue={ISSUE_IMPROVE} editor={fakeEditor} onApplied={vi.fn()} />,
    );
    expect(
      screen.getByRole("button", { name: "dialogueCoach.alternatives.apply" }),
    ).toBeInTheDocument();
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("unknown severity renders the raw value as text (still colour-not-alone)", async () => {
    const { container } = render(
      <DialogueIssueCard
        issue={{ ...ISSUE_ANALYZE, severity: "critical" }}
        editor={fakeEditor}
        onApplied={vi.fn()}
      />,
    );
    // No i18n key for "critical" → raw value shown as the visible text.
    expect(screen.getByText("critical")).toBeInTheDocument();
    expect(await runAxe(container)).toHaveNoViolations();
  });
});

describe("DialogueAlternativeCard a11y", () => {
  it("before/after blocks + Apply button, no violations", async () => {
    const { container } = render(
      <DialogueAlternativeCard
        alternative={ALT}
        originalQuote='"I am sad."'
        editor={fakeEditor}
        onApplied={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("button", { name: "dialogueCoach.alternatives.apply" }),
    ).toBeInTheDocument();
    expect(await runAxe(container)).toHaveNoViolations();
  });
});

describe("DialogueIssueList a11y + edge cases", () => {
  it("empty issues → renders the noIssues empty state and passes axe", async () => {
    const { container } = render(
      <DialogueIssueList issues={[]} editor={fakeEditor} onApplied={vi.fn()} />,
    );
    expect(screen.getByText("dialogueCoach.noIssues")).toBeInTheDocument();
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("populated list → renders each card and passes axe", async () => {
    const { container } = render(
      <DialogueIssueList
        issues={[ISSUE_ANALYZE, ISSUE_IMPROVE]}
        editor={fakeEditor}
        onApplied={vi.fn()}
      />,
    );
    expect(screen.getAllByRole("article")).toHaveLength(2);
    expect(await runAxe(container)).toHaveNoViolations();
  });
});

// ---------------------------------------------------------------------------
// Layer 2 — DialogueCoachPanel composite driven through its SSE lifecycle.
// ---------------------------------------------------------------------------

/** Build an SSE body from a sequence of JSON events. */
function sse(events: object[]): string {
  return `${events.map((e) => `data: ${JSON.stringify(e)}`).join("\n\n")}\n\ndata: [DONE]\n\n`;
}

function Panel(props?: Partial<Parameters<typeof DialogueCoachPanel>[0]>) {
  return (
    <DialogueCoachPanel
      chapterId="ch-1"
      selectionText={'"I am sad."'}
      editor={fakeEditor}
      onClose={vi.fn()}
      {...props}
    />
  );
}

describe("DialogueCoachPanel a11y (states)", () => {
  it("idle: disabled modes + select prompt, no violations", async () => {
    const { container } = render(<Panel selectionText={null} />);
    expect(screen.getByText("dialogueCoach.selectPrompt")).toBeInTheDocument();
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("idle-with-selection: enabled modes + idle hint, no violations", async () => {
    const { container } = render(<Panel />);
    // No run fired yet → the idle hint nudges toward the modes.
    expect(screen.getByText("dialogueCoach.idleHint")).toBeInTheDocument();
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("analyze result: issues without alternatives, Apply button absent, no violations", async () => {
    server.use(
      http.post("*/api/v1/ai-assist/dialogue-coach/ch-1", () =>
        HttpResponse.text(
          sse([
            {
              event: "result",
              result: {
                chapter_id: "ch-1",
                mode: "analyze",
                adaptive_summary: "",
                issues: [ISSUE_ANALYZE],
              },
            },
            { event: "done", is_final: true },
          ]),
          { headers: { "Content-Type": "text/event-stream" } },
        ),
      ),
    );
    const { container } = render(<Panel />);
    fireEvent.click(screen.getByRole("button", { name: "dialogueCoach.mode.analyze" }));
    await waitFor(() =>
      expect(screen.getByText("Telling the emotion rather than showing it.")).toBeInTheDocument(),
    );
    // Edge case (plan Step 3): analyze mode has no alternatives → no Apply.
    expect(
      screen.queryByRole("button", { name: "dialogueCoach.alternatives.apply" }),
    ).not.toBeInTheDocument();
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("improve result: alternatives + Apply button, no violations", async () => {
    server.use(
      http.post("*/api/v1/ai-assist/dialogue-coach/ch-1", () =>
        HttpResponse.text(
          sse([
            {
              event: "result",
              result: {
                chapter_id: "ch-1",
                mode: "improve",
                adaptive_summary: "Adaptive summary text.",
                issues: [ISSUE_IMPROVE],
              },
            },
            { event: "done", is_final: true },
          ]),
          { headers: { "Content-Type": "text/event-stream" } },
        ),
      ),
    );
    const { container } = render(<Panel />);
    fireEvent.click(screen.getByRole("button", { name: "dialogueCoach.mode.improve" }));
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "dialogueCoach.alternatives.apply" }),
      ).toBeInTheDocument(),
    );
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("error state: alert region + message, no violations", async () => {
    server.use(
      http.post("*/api/v1/ai-assist/dialogue-coach/ch-1", () =>
        HttpResponse.json({ detail: "upstream failed" }, { status: 500 }),
      ),
    );
    const { container } = render(<Panel />);
    fireEvent.click(screen.getByRole("button", { name: "dialogueCoach.mode.analyze" }));
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(await runAxe(container)).toHaveNoViolations();
  });
});
