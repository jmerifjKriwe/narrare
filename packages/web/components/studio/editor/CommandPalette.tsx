"use client";

import type { Editor } from "@tiptap/react";
import { AnimatePresence, motion } from "motion/react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { dialogVariants, overlayVariants } from "@/lib/motion-variants";
import { CommandPaletteResults } from "./CommandPaletteResults";
import {
  builtInCommands,
  type CommandContext,
  type CommandItem,
  type CommandState,
} from "./commands";

interface CommandPaletteProps {
  editor: Editor | null;
  isOpen: boolean;
  onClose: () => void;
  context: CommandContext;
  commandState: CommandState;
}

type RenderRow =
  | { kind: "header"; label: string }
  | { kind: "command"; index: number; command: CommandItem };

export function CommandPalette({
  editor,
  isOpen,
  onClose,
  context,
  commandState,
}: CommandPaletteProps) {
  const t = useTranslations("studio");
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const filtered = useMemo(() => {
    const visible = builtInCommands.filter((cmd) => !cmd.isVisible || cmd.isVisible(commandState));
    if (!query.trim()) return visible;
    const lower = query.toLowerCase();
    return visible.filter((cmd) => cmd.label.toLowerCase().includes(lower));
  }, [query, commandState]);

  const rows = useMemo((): RenderRow[] => {
    const result: RenderRow[] = [];
    let cmdIndex = 0;
    const formatCmds = filtered.filter((c) => c.category === "format");
    const editorCmds = filtered.filter((c) => c.category === "editor");
    const generationCmds = filtered.filter((c) => c.category === "generation");
    if (formatCmds.length > 0) {
      result.push({ kind: "header", label: t("commandPalette.categoryFormat") });
      for (const cmd of formatCmds)
        result.push({ kind: "command", index: cmdIndex++, command: cmd });
    }
    if (editorCmds.length > 0) {
      result.push({ kind: "header", label: t("commandPalette.categoryEditor") });
      for (const cmd of editorCmds)
        result.push({ kind: "command", index: cmdIndex++, command: cmd });
    }
    if (generationCmds.length > 0) {
      result.push({
        kind: "header",
        label: t("commandPalette.categoryGeneration"),
      });
      for (const cmd of generationCmds)
        result.push({ kind: "command", index: cmdIndex++, command: cmd });
    }
    return result;
  }, [filtered, t]);

  // biome-ignore lint/correctness/useExhaustiveDependencies: intentionally triggers on filtered list changes
  useEffect(() => {
    setSelectedIndex(0);
  }, [filtered]);

  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setSelectedIndex(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [isOpen]);

  const executeCommand = useCallback(
    (cmd: CommandItem) => {
      if (editor) cmd.action(editor, context);
      onClose();
    },
    [editor, context, onClose],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
        return;
      }
      if (e.key === "Enter" && filtered[selectedIndex]) {
        e.preventDefault();
        executeCommand(filtered[selectedIndex]);
      }
    },
    [filtered, selectedIndex, executeCommand, onClose],
  );

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          variants={overlayVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]"
          role="dialog"
          aria-label={t("commandPalette.title")}
        >
          <div
            className="absolute inset-0 bg-black/30 backdrop-blur-[2px]"
            onClick={onClose}
            aria-hidden="true"
          />
          <motion.div
            variants={dialogVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            className="relative w-full max-w-[500px] mx-4 bg-card rounded-lg border border-border shadow-xl overflow-hidden"
          >
            <div className="flex items-center border-b border-border px-4">
              <input
                ref={inputRef}
                type="text"
                className="flex-1 py-3 bg-transparent text-foreground text-sm outline-none placeholder:text-muted-foreground"
                placeholder={t("commandPalette.placeholder")}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
              />
            </div>
            <CommandPaletteResults
              rows={rows}
              selectedIndex={selectedIndex}
              executeCommand={executeCommand}
              onSelect={setSelectedIndex}
              noResultsLabel={t("commandPalette.noResults")}
              isFiltered={filtered.length === 0}
            />
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
