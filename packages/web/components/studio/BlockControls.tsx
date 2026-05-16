"use client";

import DragHandle from "@tiptap/extension-drag-handle-react";
import type { Editor } from "@tiptap/react";
import { GripVertical, Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useState } from "react";
import { useEditorStore } from "@/lib/stores/editorStore";

interface BlockControlsProps {
  editor: Editor | null;
}

export function BlockControls({ editor }: BlockControlsProps) {
  const t = useTranslations("studio");
  const [activePos, setActivePos] = useState<number | null>(null);
  const handleInsertBelow = useCallback(() => {
    if (!editor || activePos === null) return;

    const node = editor.state.doc.nodeAt(activePos);
    if (!node) return;

    // Insert new paragraph below the current block
    const insertPos = activePos + node.nodeSize;
    editor.chain().focus().insertContentAt(insertPos, { type: "paragraph" }).run();
  }, [editor, activePos]);

  if (!editor) return null;

  return (
    <DragHandle
      editor={editor}
      computePositionConfig={{
        placement: "left",
        strategy: "fixed",
      }}
      onNodeChange={({ pos }) => {
        setActivePos(pos);
      }}
      onElementDragStart={() => {
        useEditorStore.getState().setIsDragging(true);
      }}
      onElementDragEnd={() => {
        useEditorStore.getState().setIsDragging(false);
      }}
    >
      <div className="block-controls flex items-center gap-0.5 text-muted-foreground opacity-60 hover:opacity-100 transition-opacity duration-150">
        <button
          type="button"
          className="p-1 rounded hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
          title={t("editor.addBlock")}
          onClick={handleInsertBelow}
        >
          <Plus className="w-4 h-4" />
        </button>
        <div
          className="p-1 cursor-grab active:cursor-grabbing text-muted-foreground hover:text-foreground transition-colors"
          data-drag-handle
        >
          <GripVertical className="w-4 h-4" />
        </div>
      </div>
    </DragHandle>
  );
}
