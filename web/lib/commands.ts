import type { ComponentType } from "react";

import type { NavigateFn } from "@tanstack/react-router";

import { catalogs } from "./generated/catalogs";
import type { MessageKey } from "./i18n";

/**
 * The contract a capability's `web/commands.ts(x)` speaks: rows the palette
 * renders and runs. One-way, like the routes: a capability imports these
 * types from the shell and nothing else of it, and the generated aggregation
 * (`web/lib/generated/commands.ts`) is the one place the shell reads the
 * capabilities back.
 *
 * The modules holding the rows stay data-light on purpose — the shell
 * imports every one of them eagerly, so a component import there would drag
 * the capability into the shell bundle. A dialog loads through `openModal`'s
 * dynamic `import()` on first use instead, which keeps the capability's
 * chunk split intact.
 */

/** What the shell hands a row when the palette runs it. */
export type CommandContext = {
  /** The shell's navigation; a `to=` the router checks like any other. */
  navigate: NavigateFn;
  /** The novel the active route carries, else null — the dock rows gate on it. */
  novelId: string | null;
  /** Opens the shell's modal slot; the capability hands the lazy loader. */
  openModal: (load: () => Promise<{ default: ComponentType }>) => void;
};

/** One palette row, as a capability's `commands` array holds it. */
export type Command = {
  /** Unique across the aggregation; the tests pin it, not the compiler. */
  id: string;
  /** The catalog key the row is displayed by, in the active language. */
  titleKey: MessageKey;
  /** The effect: navigate, open a modal, or call one shell hook — nothing else. */
  run: (ctx: CommandContext) => void;
  /** Off rows do not render runnable; absent means always on. */
  enabled?: (ctx: CommandContext) => boolean;
  /** The hint the palette names beside the row, when the row has one. */
  shortcut?: string;
};

/**
 * NFD, strip combining marks, lowercase: what the palette's search compares,
 * so "öffnen" answers to "offnen" and case never decides a match.
 */
function normalize(text: string): string {
  return text.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();
}

/**
 * Whether `query` matches the row's title in any catalog's rendering. The
 * display shows the active locale, but the index reads all of them — a
 * German word finds the row from an English UI, and a mid-session language
 * switch rebuilds nothing. The catalogs are already in the bundle
 * (`web/lib/generated/catalogs.ts`).
 */
export function matchesAllLocales(titleKey: MessageKey, query: string): boolean {
  const needle = normalize(query);
  return Object.values(catalogs).some((catalog) =>
    normalize(catalog[titleKey]).includes(needle),
  );
}
