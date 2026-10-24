import { ChecksPanel } from "./ChecksPanel";
import { EntitiesPanel } from "./EntitiesPanel";
import { ExtractionPanel } from "./ExtractionPanel";

/**
 * The workspace dock surface: the novel's knowledge beside the editor —
 * extraction with its job status and review queue on top, the whole-novel
 * consistency check beside it, and the searchable entity list under both.
 * The dock's frame (the column, its close button, the tab) belongs to the
 * workspace that renders this route.
 */
export function KnowledgeDock() {
  return (
    <>
      <ExtractionPanel />
      <ChecksPanel />
      <EntitiesPanel />
    </>
  );
}
