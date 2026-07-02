import type { EditorRightPanelId } from "@/lib/stores/editorRightPanelState";
import { useEditorStore } from "@/lib/stores/editorStore";

export function useActiveEditorRightPanel(
  activeChapterId: string | null,
): EditorRightPanelId | null {
  const active = useEditorStore((s) => s.rightPanel.active);
  if (!activeChapterId) return null;
  return active;
}
