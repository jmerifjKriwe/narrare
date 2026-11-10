import type { Command } from "@shell/lib/commands";

// The capability's palette row: data only, no component imports — the
// shell's generated registry (web/lib/generated/commands.ts) imports every
// commands module eagerly, so a component import here would drag this
// capability into the shell bundle. The type import is the one-way rule:
// the capability speaks the shell's command contract, the shell never
// imports this capability's code.
export const commands = [
  {
    id: "open-structure",
    titleKey: "commands.openStructure",
    run: (ctx) => {
      // The canvas reads the novel from `?novel=` and picks one when
      // absent — so the row runs anywhere, carrying the novel along when
      // the route holds one.
      void ctx.navigate({
        to: "/planning/structure",
        search: ctx.novelId === null ? {} : { novel: ctx.novelId },
      });
    },
  },
] as const satisfies ReadonlyArray<Command>;
