import type { Editor } from "@tiptap/react";
import { Bold, Database, Heading2, Heading3, Italic, Quote, Sparkles, Wand2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { ToolbarButton } from "@/components/ui/toolbar-button";
import type {
  EditorRightPanelId,
  EditorRightPanelRequestSource,
} from "@/lib/stores/editorRightPanelState";
import { BetaReaderTrigger } from "../analysis/BetaReaderTrigger";
import { CharacterVoiceTrigger } from "../analysis/CharacterVoiceTrigger";
import { ConsistencyTrigger } from "../analysis/ConsistencyTrigger";
import { CoreferenceTrigger } from "../analysis/CoreferenceTrigger";
import { DialogueCoachTrigger } from "../analysis/DialogueCoachTrigger";
import { POVTrigger } from "../analysis/POVTrigger";
import { ReadabilityTrigger } from "../analysis/ReadabilityTrigger";
import { SentimentTrigger } from "../analysis/SentimentTrigger";
import { VoiceCheckTrigger } from "../analysis/VoiceCheckTrigger";
import { VoiceDriftTrigger } from "../analysis/VoiceDriftTrigger";
import { GhostTextConfig } from "../editor/GhostTextConfig";
import { AdaptiveStatusIndicator } from "./AdaptiveStatusIndicator";

interface EditorToolbarProps {
  editor: Editor | null;
  activeRightPanel: EditorRightPanelId | null;
  extractionPanelOpen: boolean;
  toggleRightPanel: (panel: EditorRightPanelId, requestedBy: EditorRightPanelRequestSource) => void;
  toggleExtractionPanel: () => void;
  openNameGenerator: () => void;
  onRightPanelOpenerChange: (element: HTMLElement) => void;
  /** Novel id — project id for the adaptive context query (ADR-069 D14/D15). */
  novelId: string;
}

export function EditorToolbar({
  editor,
  activeRightPanel,
  extractionPanelOpen,
  toggleRightPanel,
  toggleExtractionPanel,
  openNameGenerator,
  onRightPanelOpenerChange,
  novelId,
}: EditorToolbarProps) {
  const t = useTranslations("studio");

  if (!editor) return null;

  return (
    <div
      className="border-b border-border px-8 py-2 bg-card flex items-center gap-1"
      onClickCapture={(event) => {
        // Element (not HTMLElement) so SVG icon clicks — whose target is an
        // SVGElement/SVGPathElement — still resolve to their enclosing button.
        if (!(event.target instanceof Element)) return;
        const opener = event.target.closest<HTMLElement>("button");
        if (opener) onRightPanelOpenerChange(opener);
      }}
    >
      <ToolbarButton
        label={t("editor.bold")}
        icon={Bold}
        active={editor.isActive("bold")}
        onClick={() => editor.chain().focus().toggleBold().run()}
      />
      <ToolbarButton
        label={t("editor.italic")}
        icon={Italic}
        active={editor.isActive("italic")}
        onClick={() => editor.chain().focus().toggleItalic().run()}
      />
      <ToolbarSeparator />
      <ToolbarButton
        label={t("editor.heading2")}
        icon={Heading2}
        active={editor.isActive("heading", { level: 2 })}
        onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
      />
      <ToolbarButton
        label={t("editor.heading3")}
        icon={Heading3}
        active={editor.isActive("heading", { level: 3 })}
        onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
      />
      <ToolbarSeparator />
      <ToolbarButton
        label={t("editor.blockquote")}
        icon={Quote}
        active={editor.isActive("blockquote")}
        onClick={() => editor.chain().focus().toggleBlockquote().run()}
      />
      <ToolbarSeparator />
      <ToolbarButton
        label={t("editor.nameGenerator")}
        icon={Sparkles}
        showLabel
        onClick={openNameGenerator}
      />
      <ToolbarSeparator />
      <ToolbarButton
        label={t("editor.generate")}
        icon={Wand2}
        showLabel
        active={activeRightPanel === "generation"}
        onClick={() => toggleRightPanel("generation", "toolbar")}
      />
      <ToolbarSeparator />
      <ToolbarButton
        label={t("kb.extract")}
        icon={Database}
        showLabel
        active={extractionPanelOpen}
        onClick={toggleExtractionPanel}
      />
      <ToolbarSeparator />
      <BetaReaderTrigger />
      <SentimentTrigger />
      <ConsistencyTrigger />
      <ReadabilityTrigger />
      <POVTrigger />
      <CoreferenceTrigger />
      <CharacterVoiceTrigger />
      <VoiceCheckTrigger onClick={() => toggleRightPanel("voice_check", "toolbar")} />
      <VoiceDriftTrigger />
      <DialogueCoachTrigger />
      <ToolbarSeparator />
      <GhostTextConfig editor={editor} />
      <ToolbarSeparator />
      <AdaptiveStatusIndicator novelId={novelId} />
    </div>
  );
}

function ToolbarSeparator() {
  return <div className="w-px h-5 bg-border mx-1" />;
}
