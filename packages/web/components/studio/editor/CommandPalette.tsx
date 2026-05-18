"use client";

import type { Editor } from "@tiptap/react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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

/** Flat renderable row — either a section header or a command item. */
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

  // Filter by visibility and query
  const filtered = useMemo(() => {
    const visible = builtInCommands.filter((cmd) => !cmd.isVisible || cmd.isVisible(commandState));
    if (!query.trim()) return visible;
    const lower = query.toLowerCase();
    return visible.filter((cmd) => cmd.label.toLowerCase().includes(lower));
  }, [query, commandState]);

  // Build renderable rows with headers
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
      result.push({ kind: "header", label: t("commandPalette.categoryGeneration") });
      for (const cmd of generationCmds)
        result.push({ kind: "command", index: cmdIndex++, command: cmd });
    }
    return result;
  }, [filtered, t]);

  // Reset selection when filter changes
  // biome-ignore lint/correctness/useExhaustiveDependencies: intentionally triggers on filtered list changes
  useEffect(() => {
    setSelectedIndex(0);
  }, [filtered]);

  // Focus input when opened
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

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]"
      role="dialog"
      aria-label={t("commandPalette.title")}
    >
      <div
        className="absolute inset-0 bg-black/30 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden="true"
      />

      <div className="relative w-full max-w-[500px] mx-4 bg-card rounded-lg border border-border shadow-xl overflow-hidden">
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

        <div className="max-h-[320px] overflow-y-auto py-2">
          {rows.map((row) => {
            if (row.kind === "header") {
              return (
                <div
                  key={`header-${row.label}`}
                  className="px-4 py-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wider"
                >
                  {row.label}
                </div>
              );
            }

            const isSelected = row.index === selectedIndex;
            return (
              <button
                type="button"
                key={row.command.id}
                className={`w-full flex items-center justify-between px-4 py-2 text-sm cursor-pointer transition-colors ${
                  isSelected ? "bg-accent text-accent-foreground" : "text-foreground hover:bg-muted"
                }`}
                onClick={() => executeCommand(row.command)}
                onMouseEnter={() => setSelectedIndex(row.index)}
              >
                <span>{row.command.label}</span>
                {row.command.shortcut && (
                  <span className="text-xs text-muted-foreground font-mono">
                    {row.command.shortcut}
                  </span>
                )}
              </button>
            );
          })}

          {filtered.length === 0 && (
            <div className="px-4 py-8 text-center text-sm text-muted-foreground">
              {t("commandPalette.noResults")}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
