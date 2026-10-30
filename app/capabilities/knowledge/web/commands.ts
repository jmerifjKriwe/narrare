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
      void ctx.navigate({ to: "/novels/$id/wissen", params: { id: ctx.novelId } });
    },
    enabled: (ctx) => ctx.novelId !== null,
  },
] as const satisfies ReadonlyArray<Command>;
