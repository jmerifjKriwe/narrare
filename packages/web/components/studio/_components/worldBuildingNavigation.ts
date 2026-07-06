/**
 * Navigation/mode handlers extracted from worldBuildingState (RULE-04 / AUFG-03-04).
 *
 * Each handler sets the active KB panel mode and resets selection state
 * (entries cannot stay selected when the user navigates away from the
 * detail view). Wiki mode is special: it overlays the detail view rather
 * than replacing it, so it does not reset selection.
 */

import type { KBMode } from "../kb/kbUrlState";

interface NavigationParams {
  mode: KBMode;
  setMode: (mode: KBMode) => void;
  resetSelectionForMode: () => void;
}

/**
 * Switch to a side-panel mode that replaces the detail view.
 * Resets entry selection so stale state does not linger across views.
 */
function showPanelMode(mode: KBMode, { setMode, resetSelectionForMode }: NavigationParams): void {
  setMode(mode);
  resetSelectionForMode();
}

export function useWorldBuildingNavigation({
  mode,
  setMode,
  resetSelectionForMode,
}: NavigationParams) {
  return {
    showAnalysis: mode === "analysis",
    showConsistency: mode === "consistency",
    showGraph: mode === "graph",
    showWiki: mode === "wiki",
    handleShowAnalysis: () => showPanelMode("analysis", { mode, setMode, resetSelectionForMode }),
    handleShowConsistency: () =>
      showPanelMode("consistency", { mode, setMode, resetSelectionForMode }),
    handleShowGraph: () => showPanelMode("graph", { mode, setMode, resetSelectionForMode }),
    handleShowWiki: () => showPanelMode("wiki", { mode, setMode, resetSelectionForMode }),
    handleCloseWiki: () => setMode("detail"),
  };
}
