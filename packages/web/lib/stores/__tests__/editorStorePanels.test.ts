/**
 * editorStore panel & result tests — coverage for the toggle and set actions
 * that the base editorStore.test.ts does not exercise.
 *
 * Covers:
 *  - generic openRightPanel / closeRightPanel / toggleRightPanel
 *  - every named toggle*Panel action (open + close cycle)
 *  - toggleStoryboard / toggleExtractionPanel
 *  - setSessionActive true (opens session panel) and false (closes it)
 *  - result/loading setters (beta reader, sentiment, consistency)
 */

import { act } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { useEditorStore } from "@/lib/stores/editorStore";

function resetStore() {
  act(() => {
    useEditorStore.setState(useEditorStore.getInitialState());
  });
}

beforeEach(resetStore);

// ---------------------------------------------------------------------------
// Generic right-panel actions
// ---------------------------------------------------------------------------

describe("editorStore — generic right-panel actions", () => {
  it("openRightPanel sets the active panel and requester", () => {
    useEditorStore.getState().openRightPanel("readability", "toolbar");
    const { active, requestedBy } = useEditorStore.getState().rightPanel;
    expect(active).toBe("readability");
    expect(requestedBy).toBe("toolbar");
  });

  it("closeRightPanel clears the active panel back to closed", () => {
    useEditorStore.getState().openRightPanel("pov", "toolbar");
    useEditorStore.getState().closeRightPanel("pov");
    expect(useEditorStore.getState().rightPanel.active).toBeNull();
  });

  it("closeRightPanel with no argument closes the currently active panel", () => {
    useEditorStore.getState().openRightPanel("coreference", "toolbar");
    useEditorStore.getState().closeRightPanel();
    expect(useEditorStore.getState().rightPanel.active).toBeNull();
  });

  it("toggleRightPanel opens when closed and closes when open", () => {
    useEditorStore.getState().toggleRightPanel("metadata", "sidebar");
    expect(useEditorStore.getState().rightPanel.active).toBe("metadata");

    useEditorStore.getState().toggleRightPanel("metadata", "sidebar");
    expect(useEditorStore.getState().rightPanel.active).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Named panel toggles — each opens then closes
// ---------------------------------------------------------------------------

describe("editorStore — named panel toggles", () => {
  const cases: Array<{ name: string; call: () => void; panel: string }> = [
    {
      name: "toggleBetaReaderPanel",
      call: () => useEditorStore.getState().toggleBetaReaderPanel(),
      panel: "beta_reader",
    },
    {
      name: "toggleSentimentPanel",
      call: () => useEditorStore.getState().toggleSentimentPanel(),
      panel: "sentiment",
    },
    {
      name: "toggleConsistencyPanel",
      call: () => useEditorStore.getState().toggleConsistencyPanel(),
      panel: "consistency",
    },
    {
      name: "toggleReadabilityPanel",
      call: () => useEditorStore.getState().toggleReadabilityPanel(),
      panel: "readability",
    },
    {
      name: "togglePovPanel",
      call: () => useEditorStore.getState().togglePovPanel(),
      panel: "pov",
    },
    {
      name: "toggleCoreferencePanel",
      call: () => useEditorStore.getState().toggleCoreferencePanel(),
      panel: "coreference",
    },
    {
      name: "toggleCharacterVoicePanel",
      call: () => useEditorStore.getState().toggleCharacterVoicePanel(),
      panel: "character_voice",
    },
  ];

  for (const c of cases) {
    it(`${c.name} opens the ${c.panel} panel then closes it on second call`, () => {
      expect(useEditorStore.getState().rightPanel.active).toBeNull();

      c.call();
      expect(useEditorStore.getState().rightPanel.active).toBe(c.panel);

      c.call();
      expect(useEditorStore.getState().rightPanel.active).toBeNull();
    });
  }

  it("opening a second panel is mutually exclusive (previous is tracked)", () => {
    useEditorStore.getState().toggleBetaReaderPanel();
    useEditorStore.getState().toggleSentimentPanel();

    const panel = useEditorStore.getState().rightPanel;
    expect(panel.active).toBe("sentiment");
    expect(panel.previous).toBe("beta_reader");
  });
});

// ---------------------------------------------------------------------------
// Storyboard / extraction toggles
// ---------------------------------------------------------------------------

describe("editorStore — storyboard & extraction toggles", () => {
  it("toggleStoryboard flips storyboardOpen", () => {
    expect(useEditorStore.getState().storyboardOpen).toBe(false);
    useEditorStore.getState().toggleStoryboard();
    expect(useEditorStore.getState().storyboardOpen).toBe(true);
    useEditorStore.getState().toggleStoryboard();
    expect(useEditorStore.getState().storyboardOpen).toBe(false);
  });

  it("toggleExtractionPanel flips extractionPanelOpen", () => {
    expect(useEditorStore.getState().extractionPanelOpen).toBe(false);
    useEditorStore.getState().toggleExtractionPanel();
    expect(useEditorStore.getState().extractionPanelOpen).toBe(true);
    useEditorStore.getState().toggleExtractionPanel();
    expect(useEditorStore.getState().extractionPanelOpen).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Session active (drives right-panel open/close)
// ---------------------------------------------------------------------------

describe("editorStore — setSessionActive", () => {
  it("activating opens the session panel via recovery", () => {
    useEditorStore.getState().setSessionActive(true);
    expect(useEditorStore.getState().sessionActive).toBe(true);
    expect(useEditorStore.getState().rightPanel.active).toBe("session");
    expect(useEditorStore.getState().rightPanel.requestedBy).toBe("recovery");
  });

  it("deactivating closes the session panel", () => {
    useEditorStore.getState().setSessionActive(true);
    useEditorStore.getState().setSessionActive(false);

    expect(useEditorStore.getState().sessionActive).toBe(false);
    expect(useEditorStore.getState().rightPanel.active).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Result / loading setters
// ---------------------------------------------------------------------------

describe("editorStore — result & loading setters", () => {
  it("setBetaReaderResult stores and clears the beta reader result", () => {
    const result = { novel_id: "n1" } as never;
    useEditorStore.getState().setBetaReaderResult(result);
    expect(useEditorStore.getState().betaReaderResult).toBe(result);
    useEditorStore.getState().setBetaReaderResult(null);
    expect(useEditorStore.getState().betaReaderResult).toBeNull();
  });

  it("setBetaReaderLoading toggles the loading flag", () => {
    useEditorStore.getState().setBetaReaderLoading(true);
    expect(useEditorStore.getState().betaReaderLoading).toBe(true);
    useEditorStore.getState().setBetaReaderLoading(false);
    expect(useEditorStore.getState().betaReaderLoading).toBe(false);
  });

  it("setSentimentResult stores and clears the sentiment result", () => {
    const result = [{ sentence_count: 1 }] as never;
    useEditorStore.getState().setSentimentResult(result);
    expect(useEditorStore.getState().sentimentResult).toBe(result);
    useEditorStore.getState().setSentimentResult(null);
    expect(useEditorStore.getState().sentimentResult).toBeNull();
  });

  it("setSentimentLoading toggles the loading flag", () => {
    useEditorStore.getState().setSentimentLoading(true);
    expect(useEditorStore.getState().sentimentLoading).toBe(true);
  });

  it("setConsistencyResult stores and clears the consistency result", () => {
    const result = { novel_id: "n1", total_issues: 0 } as never;
    useEditorStore.getState().setConsistencyResult(result);
    expect(useEditorStore.getState().consistencyResult).toBe(result);
    useEditorStore.getState().setConsistencyResult(null);
    expect(useEditorStore.getState().consistencyResult).toBeNull();
  });

  it("setConsistencyLoading toggles the loading flag", () => {
    useEditorStore.getState().setConsistencyLoading(true);
    expect(useEditorStore.getState().consistencyLoading).toBe(true);
    useEditorStore.getState().setConsistencyLoading(false);
    expect(useEditorStore.getState().consistencyLoading).toBe(false);
  });
});
