/**
 * Task 11 — Dialogue Coach editor wiring.
 *
 * Integration-level assertions that the shipped pieces are COMPOSED into the
 * editor (ADR-069 Decision 16): the `dialogue_coach` panel id is registered,
 * the panel renders when active with the editor's live selection threaded into
 * its props, and the toolbar exposes the trigger + the Adaptive Status
 * Indicator.
 *
 * The Dialogue Coach panel's own behaviour (modes, SSE, alternatives) is owned
 * by Task 8's DialogueCoachPanel.test.tsx; here the panel is stubbed so this
 * test stays focused on the wiring contract (activePanel → render + selection
 * threading). Likewise the indicator's 3-state logic is owned by Task 9; here
 * we only assert it is composed into the toolbar.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { Editor } from "@tiptap/react";
import { HttpResponse, http } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { server } from "@/mocks/server";
import { EditorPanelContent } from "../EditorPanelContent";
import { EditorToolbar } from "../EditorToolbar";

// Stub the heavy panel: assert only that the wiring threads chapterId +
// selectionText into it (the panel's internals are Task 8's concern).
vi.mock("../../analysis/DialogueCoachPanel", () => ({
  DialogueCoachPanel: ({
    selectionText,
    chapterId,
  }: {
    selectionText: string | null;
    chapterId: string;
    // editor + onClose are part of the contract but not asserted here.
  }) => (
    <div data-testid="dialogue-coach-panel">
      <span data-testid="dc-chapter">{chapterId}</span>
      <span data-testid="dc-selection">{selectionText ?? "<none>"}</span>
    </div>
  ),
}));

// Other analysis triggers pull from useEditorStore; stub them so the toolbar
// test isolates the Dialogue Coach trigger + indicator wiring.
vi.mock("../../analysis/BetaReaderTrigger", () => ({
  BetaReaderTrigger: () => <div data-testid="beta-reader-trigger" />,
}));
vi.mock("../../analysis/SentimentTrigger", () => ({
  SentimentTrigger: () => <div data-testid="sentiment-trigger" />,
}));
vi.mock("../../analysis/ConsistencyTrigger", () => ({
  ConsistencyTrigger: () => <div data-testid="consistency-trigger" />,
}));
vi.mock("../../analysis/ReadabilityTrigger", () => ({
  ReadabilityTrigger: () => <div data-testid="readability-trigger" />,
}));
vi.mock("../../analysis/POVTrigger", () => ({
  POVTrigger: () => <div data-testid="pov-trigger" />,
}));
vi.mock("../../analysis/CoreferenceTrigger", () => ({
  CoreferenceTrigger: () => <div data-testid="coreference-trigger" />,
}));
vi.mock("../../analysis/CharacterVoiceTrigger", () => ({
  CharacterVoiceTrigger: () => <div data-testid="character-voice-trigger" />,
}));
vi.mock("../../analysis/VoiceCheckTrigger", () => ({
  VoiceCheckTrigger: () => <div data-testid="voice-check-trigger" />,
}));
vi.mock("../../editor/GhostTextConfig", () => ({
  GhostTextConfig: () => <div data-testid="ghost-text-config" />,
}));

// Dialogue Coach trigger toggles the panel via the editor store. Capture the
// call to assert the toolbar→store wiring.
const toggleRightPanel = vi.fn();
let activePanel: string | null = null;
vi.mock("@/lib/stores/editorStore", () => ({
  useEditorStore: vi.fn((selector?: (s: Record<string, unknown>) => unknown) => {
    const state = {
      rightPanel: { active: activePanel, previous: null, requestedBy: null },
      toggleRightPanel,
    };
    return selector ? selector(state) : state;
  }),
}));

/** Minimal editor stub for the toolbar (isActive + chain) + selection read. */
function makeFakeEditor(selection: string | null = null): Editor {
  const len = selection ? selection.length : 0;
  const chain: Record<string, ReturnType<typeof vi.fn>> = {};
  chain.focus = vi.fn(() => chain);
  chain.toggleBold = vi.fn(() => chain);
  chain.toggleItalic = vi.fn(() => chain);
  chain.toggleHeading = vi.fn(() => chain);
  chain.toggleBlockquote = vi.fn(() => chain);
  chain.run = vi.fn();
  return {
    isActive: () => false,
    chain: () => chain,
    state: {
      selection: { from: 0, to: len, empty: len === 0 },
      doc: { textBetween: (f: number, t: number) => (selection ?? "").slice(0, t - f) },
    },
    on: () => {},
    off: () => {},
  } as unknown as Editor;
}

function withQueryClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const panelBaseProps = {
  novelId: "novel-1",
  activeChapterId: "ch-1",
  content: "<p>x</p>",
  chapter: undefined,
  chapters: [],
  sessionStartWordCount: 0,
  volumeStats: undefined,
  wordCount: 1,
  charCount: 1,
  paragraphCount: 1,
  sessionMode: "interactive_session" as const,
  handleSessionClose: vi.fn(),
  handleDraftAccepted: vi.fn(),
  handleStartSession: vi.fn(),
  closePanel: vi.fn(),
};

afterEach(() => {
  server.resetHandlers();
  toggleRightPanel.mockClear();
  activePanel = null;
});

describe("dialogue_coach panel wiring", () => {
  it("renders the Dialogue Coach panel when active and threads the editor selection", () => {
    const editor = makeFakeEditor('"I am sad."');
    render(<EditorPanelContent {...panelBaseProps} activePanel="dialogue_coach" editor={editor} />);

    expect(screen.getByTestId("dialogue-coach-panel")).toBeInTheDocument();
    expect(screen.getByTestId("dc-chapter")).toHaveTextContent("ch-1");
    expect(screen.getByTestId("dc-selection")).toHaveTextContent('"I am sad."');
  });

  it("threads null when nothing is selected", () => {
    const editor = makeFakeEditor(null);
    render(<EditorPanelContent {...panelBaseProps} activePanel="dialogue_coach" editor={editor} />);

    expect(screen.getByTestId("dc-selection")).toHaveTextContent("<none>");
  });
});

describe("EditorToolbar — Dialogue Coach trigger + Adaptive Status Indicator", () => {
  // The indicator always mounts in the toolbar and reads the adaptive context.
  // Give it a deterministic default so tests stay hermetic (no real network);
  // individual tests override with server.use() when they assert a state.
  beforeEach(() => {
    server.use(
      http.get("*/api/v1/adaptive/novel-1/context", () =>
        HttpResponse.json({
          project_id: "novel-1",
          enabled: false,
          has_any_signal: false,
          weights: { preference: 0.5, voice_fidelity: 0.5, style_constraints: 0.5, avoidance: 0.5 },
          sources: {
            preference_text: "",
            voice_profiles_text: "",
            style_constraints_text: "",
            avoidance_patterns_text: "",
          },
        }),
      ),
    );
  });

  it("renders the Dialogue Coach trigger and the Adaptive Status Indicator", async () => {
    server.use(
      http.get("*/api/v1/adaptive/novel-1/context", () =>
        HttpResponse.json({
          project_id: "novel-1",
          enabled: true,
          has_any_signal: true,
          weights: { preference: 0.5, voice_fidelity: 0.5, style_constraints: 0.5, avoidance: 0.5 },
          sources: {
            preference_text: "",
            voice_profiles_text: "",
            style_constraints_text: "",
            avoidance_patterns_text: "",
          },
        }),
      ),
    );

    withQueryClient(
      <EditorToolbar
        editor={makeFakeEditor()}
        activeRightPanel={null}
        extractionPanelOpen={false}
        toggleRightPanel={vi.fn()}
        toggleExtractionPanel={vi.fn()}
        openNameGenerator={vi.fn()}
        onRightPanelOpenerChange={vi.fn()}
        novelId="novel-1"
      />,
    );

    // Trigger (accessible name = dialogueCoach.triggerTooltip under the root
    // namespace convention — matches DialogueCoachPanel).
    expect(
      screen.getByRole("button", { name: "dialogueCoach.triggerTooltip" }),
    ).toBeInTheDocument();

    // Indicator renders its active-state button.
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "indicator.active" })).toBeInTheDocument(),
    );
  });

  it("opens the dialogue_coach panel when the trigger is clicked", () => {
    withQueryClient(
      <EditorToolbar
        editor={makeFakeEditor()}
        activeRightPanel={null}
        extractionPanelOpen={false}
        toggleRightPanel={toggleRightPanel}
        toggleExtractionPanel={vi.fn()}
        openNameGenerator={vi.fn()}
        onRightPanelOpenerChange={vi.fn()}
        novelId="novel-1"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "dialogueCoach.triggerTooltip" }));

    expect(toggleRightPanel).toHaveBeenCalledWith("dialogue_coach", "toolbar");
  });
});
