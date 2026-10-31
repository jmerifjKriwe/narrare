import type { Command } from "@shell/lib/commands";

// The capability's palette rows: data only, no component imports — the
// shell's generated registry (web/lib/generated/commands.ts) imports every
// commands module eagerly, so a component import here would drag this
// capability into the shell bundle. The type import is the one-way rule:
// the capability speaks the shell's command contract, the shell never
// imports this capability's code.
export const commands = [
  {
    id: "open-settings",
    titleKey: "commands.openSettings",
    run: (ctx) => {
      void ctx.navigate({ to: "/settings" });
    },
  },
] as const satisfies ReadonlyArray<Command>;
