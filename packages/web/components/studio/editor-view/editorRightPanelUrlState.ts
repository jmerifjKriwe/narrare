import type { EditorRightPanelId } from "@/lib/stores/editorRightPanelState";
import { isEditorRightPanelId } from "@/lib/stores/editorRightPanelState";

const UNSAFE_DEEP_LINK_PANELS = new Set<EditorRightPanelId>(["session"]);

export function parseEditorRightPanelParam(value: string | null): EditorRightPanelId | null {
  if (!isEditorRightPanelId(value)) return null;
  if (UNSAFE_DEEP_LINK_PANELS.has(value)) return null;
  return value;
}

export function serializeEditorRightPanelParam(panel: EditorRightPanelId | null): string | null {
  if (panel === null || UNSAFE_DEEP_LINK_PANELS.has(panel)) return null;
  return panel;
}
