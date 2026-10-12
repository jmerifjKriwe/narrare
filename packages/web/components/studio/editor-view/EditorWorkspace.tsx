import { TipTapEditor } from "../TipTapEditor";
import type { EditorSurfaceProps } from "./types";

export function EditorWorkspace({
  novelId,
  activeChapterId,
  content,
  setContent,
  handleAutosave,
  slashCommandHandlers,
}: EditorSurfaceProps) {
  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-4xl mx-auto">
        <TipTapEditor
          content={content}
          onChange={setContent}
          onAutosave={handleAutosave}
          autosaveInterval={30_000}
          chapterId={activeChapterId}
          novelId={novelId}
          slashCommandHandlers={slashCommandHandlers}
        />
      </div>
    </div>
  );
}
