import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DialogueCoachPanel } from "@/components/studio/analysis/DialogueCoachPanel";
import { server } from "@/mocks/server";

const fakeEditor = {
  getHTML: () => "<p>I am sad.</p>",
  state: { doc: { textBetween: () => "I am sad." } },
  chain: () => ({ focus: () => ({ setContent: vi.fn(), run: () => {} }) }),
} as unknown as Parameters<typeof DialogueCoachPanel>[0]["editor"];

function sse(events: object[]): string {
  return `${events.map((e) => `data: ${JSON.stringify(e)}`).join("\n\n")}\n\ndata: [DONE]\n\n`;
}

afterEach(() => server.resetHandlers());

describe("DialogueCoachPanel", () => {
  it("idle: shows a run CTA disabled when no selection", () => {
    render(
      <DialogueCoachPanel
        chapterId="ch-1"
        selectionText={null}
        editor={fakeEditor}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByText("dialogueCoach.selectPrompt")).toBeInTheDocument();
  });

  it("runs analyze and renders issues without alternatives", async () => {
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
                issues: [
                  {
                    issue_type: "on-the-nose",
                    speaker: "Alice",
                    original_quote: '"I am sad."',
                    diagnosis: "telling, not showing",
                    severity: "medium",
                    alternatives: null,
                  },
                ],
              },
            },
            { event: "done", is_final: true },
          ]),
          { headers: { "Content-Type": "text/event-stream" } },
        ),
      ),
    );
    render(
      <DialogueCoachPanel
        chapterId="ch-1"
        selectionText={'"I am sad."'}
        editor={fakeEditor}
        onClose={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "dialogueCoach.mode.analyze" }));
    await waitFor(() => expect(screen.getByText("telling, not showing")).toBeInTheDocument());
    expect(screen.queryByText("dialogueCoach.alternatives.apply")).not.toBeInTheDocument();
  });

  it("improve mode renders before/after blocks and an Apply button", async () => {
    server.use(
      http.post("*/api/v1/ai-assist/dialogue-coach/ch-1", () =>
        HttpResponse.text(
          sse([
            {
              event: "result",
              result: {
                chapter_id: "ch-1",
                mode: "improve",
                adaptive_summary: "",
                issues: [
                  {
                    issue_type: "on-the-nose",
                    speaker: "Alice",
                    original_quote: '"I am sad."',
                    diagnosis: "telling",
                    severity: "medium",
                    alternatives: [
                      { rewrite: '"Her shoulders slumped."', explanation: "show emotion" },
                    ],
                  },
                ],
              },
            },
            { event: "done", is_final: true },
          ]),
          { headers: { "Content-Type": "text/event-stream" } },
        ),
      ),
    );
    render(
      <DialogueCoachPanel
        chapterId="ch-1"
        selectionText={'"I am sad."'}
        editor={fakeEditor}
        onClose={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "dialogueCoach.mode.improve" }));
    await waitFor(() => expect(screen.getByText('"I am sad."')).toBeInTheDocument());
    expect(screen.getByText('"Her shoulders slumped."')).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "dialogueCoach.alternatives.apply" }),
    ).toBeInTheDocument();
  });
});
