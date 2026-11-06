import { createElement, useState } from "react";

import type { Command } from "@shell/lib/commands";

// The capability's palette rows: data only, no component imports — the
// shell's generated registry (web/lib/generated/commands.ts) imports every
// commands module eagerly, so a component import here would drag this
// capability into the shell bundle. The type import is the one-way rule:
// the capability speaks the shell's command contract, the shell never
// imports this capability's code.
export const commands = [
  {
    id: "open-wissen-dock",
    titleKey: "commands.openWissenDock",
    // The dock lives at a novel: without one the row is off, and `run`
    // guards on the same fact instead of trusting it — a palette never
    // runs an off row, so the guard only ever fires from a stale context.
    run: (ctx) => {
      if (ctx.novelId === null) return;
      void ctx.navigate({
        to: "/novels/$id/wissen",
        params: { id: ctx.novelId },
        // The dock opens where the workbench stood: an absent `search` is
        // the router's empty record, and it would wipe the address — the
        // chapter a reload or share reads back, and the ?rail/?focus panel
        // state. `search: true` carries it, the way the palette's dock rows
        // and the workbench's own tabs do.
        search: true,
      });
    },
    enabled: (ctx) => ctx.novelId !== null,
  },
  {
    id: "run-extraction",
    titleKey: "commands.runExtraction",
    run: (ctx) => {
      if (ctx.novelId === null) return;
      const novelId = ctx.novelId;
      ctx.openModal(async () => {
        const m = await import("./JobDialogs");
        return {
          // The slot mounts a props-free component: the dialog reads the
          // chapter list through Query (the workbench already asked for it)
          // and mounts already open — the palette row was the press.
          // Closing it unmounts the overlay; the slot's next open is a
          // fresh mount.
          default: function ExtractionJobFromPalette() {
            const [open, setOpen] = useState(true);
            return createElement(m.ExtractionJobDialog, {
              novelId,
              isOpen: open,
              onOpenChange: setOpen,
            });
          },
        };
      });
    },
    enabled: (ctx) => ctx.novelId !== null,
  },
  {
    id: "run-consistency-check",
    titleKey: "commands.checkConsistency",
    run: (ctx) => {
      if (ctx.novelId === null) return;
      const novelId = ctx.novelId;
      ctx.openModal(async () => {
        const m = await import("./JobDialogs");
        return {
          // Like the extraction row: the dialog mounts already open, and
          // its close unmounts the overlay.
          default: function ConsistencyCheckFromPalette() {
            const [open, setOpen] = useState(true);
            return createElement(m.ConsistencyCheckDialog, {
              novelId,
              isOpen: open,
              onOpenChange: setOpen,
            });
          },
        };
      });
    },
    enabled: (ctx) => ctx.novelId !== null,
  },
] as const satisfies ReadonlyArray<Command>;
