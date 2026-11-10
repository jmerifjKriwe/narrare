import { useState } from "react";

import { useTranslation } from "@shell/lib/i18n";
import { Button } from "@shell/ui/Button";

import { ChecksPanel } from "./ChecksPanel";
import { EntitiesPanel } from "./EntitiesPanel";
import { ExtractionPanel } from "./ExtractionPanel";
import { NeighborhoodLens } from "./NeighborhoodLens";

type DockView = "list" | "neighborhood";

/**
 * The workspace dock surface: the novel's knowledge beside the editor —
 * either today's stacking (extraction with its job status and review queue
 * on top, the whole-novel consistency check beside it, and the searchable
 * entity list under both) or the selected entity's neighborhood lens. One
 * switcher, two options, no new dock tab: the lens is a view of this dock,
 * not a place beside it. The dock's frame (the column, its close button,
 * the tab) belongs to the workspace that renders this route.
 */
export function KnowledgeDock() {
  const t = useTranslation();
  // Local state, not the URL: the view is how the dock is looked at, while
  // the selection (`?entity=`) is what it looks at — the address carries
  // the entity across the switch, so the lens opens on the listed row.
  const [view, setView] = useState<DockView>("list");

  return (
    <>
      {/* The two-option switcher: the storyboard's remap idiom — a labeled
          group of two buttons, the standing one pressed. */}
      <div className="flex flex-wrap gap-2" role="group" aria-label={t("knowledge.dockViewLabel")}>
        <Button
          variant="secondary"
          aria-pressed={view === "list"}
          onClick={() => setView("list")}
        >
          {t("knowledge.dockViewList")}
        </Button>
        <Button
          variant="secondary"
          aria-pressed={view === "neighborhood"}
          onClick={() => setView("neighborhood")}
        >
          {t("knowledge.dockViewNeighborhood")}
        </Button>
      </div>
      {view === "list" ? (
        <>
          <ExtractionPanel />
          <ChecksPanel />
          <EntitiesPanel />
        </>
      ) : (
        <NeighborhoodLens />
      )}
    </>
  );
}
