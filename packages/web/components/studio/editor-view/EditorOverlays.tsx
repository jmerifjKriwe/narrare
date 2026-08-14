import type { QueryClient } from "@tanstack/react-query";
import type { Editor } from "@tiptap/react";
import { AnimatePresence } from "motion/react";
import { CommandPalette } from "../editor/CommandPalette";
import type { CommandContext, CommandState } from "../editor/commands";
import { ExportPanel } from "../export/ExportPanel";
import { ExtractionPanel } from "../extraction/ExtractionPanel";
import { NameGeneratorModal } from "../generation/NameGeneratorModal";

interface EditorOverlaysProps {
  editor: Editor | null;
  novelId: string;
  activeChapterId: string;
  commandPaletteOpen: boolean;
  setCommandPaletteOpen: (open: boolean) => void;
  commandContext: CommandContext;
  commandState: CommandState;
  nameGeneratorOpen: boolean;
  setNameGeneratorOpen: (open: boolean) => void;
  extractionPanelOpen: boolean;
  toggleExtractionPanel: () => void;
  exportOpen: boolean;
  setExportOpen: (open: boolean) => void;
  queryClient: QueryClient;
}

export function EditorOverlays({
  editor,
  novelId,
  activeChapterId,
  commandPaletteOpen,
  setCommandPaletteOpen,
  commandContext,
  commandState,
  nameGeneratorOpen,
  setNameGeneratorOpen,
  extractionPanelOpen,
  toggleExtractionPanel,
  exportOpen,
  setExportOpen,
  queryClient,
}: EditorOverlaysProps) {
  return (
    <>
      <CommandPalette
        editor={editor}
        isOpen={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
        context={commandContext}
        commandState={commandState}
      />
      <NameGeneratorModal
        novelId={novelId}
        isOpen={nameGeneratorOpen}
        onClose={() => setNameGeneratorOpen(false)}
      />
      <ExportPanel novelId={novelId} isOpen={exportOpen} onClose={() => setExportOpen(false)} />
      <AnimatePresence>
        {extractionPanelOpen && (
          <ExtractionPanel
            novelId={novelId}
            chapterId={activeChapterId}
            onClose={toggleExtractionPanel}
            onApplied={() => {
              void queryClient.invalidateQueries({ queryKey: ["kb", novelId] });
            }}
          />
        )}
      </AnimatePresence>
    </>
  );
}
