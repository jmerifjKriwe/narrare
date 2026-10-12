/**
 * Mounts the CoAuthorPanel modal overlay while a co-author selection is
 * active (audit B09). Pure host: flow state and handlers live in
 * `useEditorAiEntryPoints`; this component only decides panel visibility.
 *
 * @module CoAuthorOverlay
 */

import { CoAuthorPanel } from "../editor/CoAuthorPanel";
import type { CoAuthorFlow } from "./useEditorAiEntryPoints";

interface CoAuthorOverlayProps {
  novelId: string;
  chapterId: string;
  flow: CoAuthorFlow;
}

export function CoAuthorOverlay({ novelId, chapterId, flow }: CoAuthorOverlayProps) {
  if (!flow.selection) return null;
  return (
    <CoAuthorPanel
      novelId={novelId}
      chapterId={chapterId}
      selectionText={flow.selection.text}
      contextBefore={flow.selection.contextBefore}
      contextAfter={flow.selection.contextAfter}
      onAccept={flow.accept}
      onClose={flow.close}
    />
  );
}
