"use client";

import type { CommandItem } from "./commands";

type RenderRow =
  | { kind: "header"; label: string }
  | { kind: "command"; index: number; command: CommandItem };

interface CommandPaletteResultsProps {
  rows: RenderRow[];
  selectedIndex: number;
  executeCommand: (cmd: CommandItem) => void;
  onSelect: (index: number) => void;
  noResultsLabel: string;
  isFiltered: boolean;
}

export function CommandPaletteResults({
  rows,
  selectedIndex,
  executeCommand,
  onSelect,
  noResultsLabel,
  isFiltered,
}: CommandPaletteResultsProps) {
  return (
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
            onMouseEnter={() => onSelect(row.index)}
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
      {isFiltered && (
        <div className="px-4 py-8 text-center text-sm text-muted-foreground">{noResultsLabel}</div>
      )}
    </div>
  );
}
