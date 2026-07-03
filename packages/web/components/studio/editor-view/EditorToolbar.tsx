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
import { POVTrigger } from "../analysis/POVTrigger";
import { ReadabilityTrigger } from "../analysis/ReadabilityTrigger";
import { SentimentTrigger } from "../analysis/SentimentTrigger";
import { VoiceCheckTrigger } from "../analysis/VoiceCheckTrigger";
import { GhostTextConfig } from "../editor/GhostTextConfig";

interface EditorToolbarProps {
  editor: Editor | null;
  activeRightPanel: EditorRightPanelId | null;
  extractionPanelOpen: boolean;
  toggleRightPanel: (panel: EditorRightPanelId, requestedBy: EditorRightPanelRequestSource) => void;
  toggleExtractionPanel: () => void;
  openNameGenerator: () => void;
  onRightPanelOpenerChange: (element: HTMLElement) => void;
}

export function EditorToolbar({
  editor,
  activeRightPanel,
  extractionPanelOpen,
  toggleRightPanel,
  toggleExtractionPanel,
  openNameGenerator,
  onRightPanelOpenerChange,
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
      <button
        type="button"
        onClick={openNameGenerator}
        className="flex items-center gap-1.5 px-2.5 py-1 rounded hover:bg-accent transition-colors text-sm text-primary"
        title={t("editor.nameGenerator")}
      >
        <Sparkles className="w-3.5 h-3.5" />
        <span>{t("editor.nameGenerator")}</span>
      </button>
      <ToolbarSeparator />
      <button
        type="button"
        onClick={() => toggleRightPanel("generation", "toolbar")}
        className={`flex items-center gap-1.5 px-2.5 py-1 rounded hover:bg-accent transition-colors text-sm text-primary ${
          activeRightPanel === "generation" ? "bg-accent" : ""
        }`}
        title={t("editor.generate")}
      >
        <Wand2 className="w-3.5 h-3.5" />
        <span>{t("editor.generate")}</span>
      </button>
      <ToolbarSeparator />
      <button
        type="button"
        onClick={toggleExtractionPanel}
        className={`flex items-center gap-1.5 px-2.5 py-1 rounded hover:bg-accent transition-colors text-sm text-primary ${
          extractionPanelOpen ? "bg-accent" : ""
        }`}
        title={t("kb.extract")}
      >
        <Database className="w-3.5 h-3.5" />
        <span>{t("kb.extract")}</span>
      </button>
      <ToolbarSeparator />
      <BetaReaderTrigger />
      <SentimentTrigger />
      <ConsistencyTrigger />
      <ReadabilityTrigger />
      <POVTrigger />
      <CoreferenceTrigger />
      <CharacterVoiceTrigger />
      <VoiceCheckTrigger onClick={() => toggleRightPanel("voice_check", "toolbar")} />
      <ToolbarSeparator />
      <GhostTextConfig editor={editor} />
    </div>
  );
}

function ToolbarSeparator() {
  return <div className="w-px h-5 bg-border mx-1" />;
}
