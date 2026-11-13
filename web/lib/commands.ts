import type { ComponentType } from "react";

import type { NavigateFn } from "@tanstack/react-router";

import { catalogs } from "./generated/catalogs";
import type { MessageKey } from "./i18n";
import { normalize } from "./search";

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
  /** The chapter the active route carries, else null — the rows pass it on. */
  chapterId: string | null;
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
};

/**
 * Whether `query` matches the row's title in any catalog's rendering. The
 * display shows the active locale, but the index reads all of them — a
 * German word finds the row from an English UI, and a mid-session language
 * switch rebuilds nothing. The catalogs are already in the bundle
 * (`web/lib/generated/catalogs.ts`). The query is trimmed here: the palette
 * hands the field's value through whole, and whitespace must not become
 * part of the needle. The normalization itself is `lib/search.ts`'s — the
 * one definition the rail's filter shares.
 */
export function matchesAllLocales(titleKey: MessageKey, query: string): boolean {
  const needle = normalize(query.trim());
  return Object.values(catalogs).some((catalog) =>
    normalize(catalog[titleKey]).includes(needle),
  );
}

/**
 * The palette's matcher for rows that own their words instead of a catalog
 * key — a chapter's title (and its localized default), an entity's name,
 * aliases and tags, a novel's title. The same normalization and the same
 * trim as `matchesAllLocales`, so one search semantics covers the keyed
 * rows and the data rows alike.
 */
/**
 * The palette's matcher for rows that own their words instead of a catalog
 * key — a chapter's title (and its localized default), an entity's name,
 * aliases and tags, a novel's title. The same normalization and the same
 * trim as `matchesAllLocales`, so one search semantics covers the keyed
 * rows and the data rows alike.
 */
export function matchesAnyText(query: string, texts: string[]): boolean {
  const needle = normalize(query.trim());
  return texts.some((text) => normalize(text).includes(needle));
}

/**
 * Chapter rows own their words (the chapter's title, or its localized
 * default). Matching them across every catalog's rendering of the default
 * title — not just the active one — is what lets a German word find the
 * row from an English UI. The `{n}` placeholder is interpolated per
 * catalog before matching, so "Kapitel 3" finds "Chapter 3"'s row too.
 */
export function matchesChapterRow(
  query: string,
  chapter: { title: string; position: number },
): boolean {
  const needle = normalize(query.trim());
  if (normalize(chapter.title).includes(needle)) return true;
  const n = chapter.position + 1;
  return Object.values(catalogs).some((catalog) => {
    const template = catalog["chapters.defaultTitle" as MessageKey];
    if (typeof template !== "string") return false;
    return normalize(template.replace(/\{n\}/g, String(n))).includes(needle);
  });
}
