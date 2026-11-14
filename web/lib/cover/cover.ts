/**
 * The cover's model: genre → channel, the variant axis, size detail tiers and
 * edge normalization — everything the book object needs before it renders.
 *
 * Pure: no React, no i18n, no state. The ground/ink values are token *names*
 * (`cover-ink`, `cover-fantasy-ink`, …); the tokens themselves live in
 * globals.css and the component resolves them, so this module stays testable
 * in node and never touches the palette.
 *
 * The rulings the edges obey: a short title is exactly one word — "Dead
 * Signal" is not short, "Echo" is, however long a single word grows; a long
 * title is more than 60 trimmed characters and lets the vignette recede;
 * Lyrik and every unknown genre fall to the neutral fallback (owner decision
 * 2026-11-14), never to a crash or a blank cover.
 */

import { murmur3_32 } from "./hash";

export type CoverChannel =
  | "scifi"
  | "fantasy"
  | "mystery"
  | "literary"
  | "historical"
  | "romance"
  | "thriller"
  | "fallback";

export type CoverSize = "wizard" | "hero" | "shelf" | "mini";

/** The four canonical view sizes (spec Sektion 04), in CSS pixels. */
export const COVER_SIZES: Record<CoverSize, { width: number; height: number }> = {
  wizard: { width: 224, height: 300 },
  hero: { width: 192, height: 264 },
  shelf: { width: 144, height: 200 },
  mini: { width: 36, height: 48 },
};

/**
 * The genre labels the cover knows, already trimmed and lowercased. English
 * canonical labels plus the German ones the setup speaks; anything else —
 * including Lyrik and Essayistik, deliberately outside the matrix — falls
 * back. A fixed map, not a guess: an unknown genre must never pick a pigment.
 */
const CHANNEL_ALIASES: Record<string, CoverChannel | undefined> = {
  "science fiction": "scifi",
  "science-fiction": "scifi",
  "sci-fi": "scifi",
  scifi: "scifi",
  "sci fi": "scifi",
  fantasy: "fantasy",
  mystery: "mystery",
  krimi: "mystery",
  literary: "literary",
  "literary fiction": "literary",
  "literarische belletristik": "literary",
  historical: "historical",
  "historical fiction": "historical",
  "historischer roman": "historical",
  romance: "romance",
  liebesroman: "romance",
  thriller: "thriller",
};

/** The genre's ground and ink token names; mystery/literary/historical/scifi
 * reuse the legacy palette, the four new channels are theme-constant. */
const CHANNEL_TOKENS: Record<CoverChannel, { ground: string; ink: string }> = {
  scifi: { ground: "cover-ink", ink: "cover-ink-ink" },
  fantasy: { ground: "cover-fantasy", ink: "cover-fantasy-ink" },
  mystery: { ground: "cover-pale", ink: "cover-pale-ink" },
  literary: { ground: "cover-sepia", ink: "cover-sepia-ink" },
  historical: { ground: "cover-slate", ink: "cover-slate-ink" },
  romance: { ground: "cover-romance", ink: "cover-romance-ink" },
  thriller: { ground: "cover-thriller", ink: "cover-thriller-ink" },
  fallback: { ground: "cover-fallback", ink: "cover-fallback-ink" },
};

/** The channel a genre label lands on; absent, empty or unknown → fallback. */
export function channelFor(genre: string | null | undefined): CoverChannel {
  const key = (genre ?? "").trim().toLowerCase();
  return CHANNEL_ALIASES[key] ?? "fallback";
}

/** The layout variant: 0 centered, 1 offset/diagonal, 2 monumental whitespace.
 * The title hash spreads same-genre books over the three axes, deterministically. */
export function variantFor(title: string): 0 | 1 | 2 {
  return (murmur3_32(title) % 3) as 0 | 1 | 2;
}

export interface CoverModel {
  channel: CoverChannel;
  variant: 0 | 1 | 2;
  groundToken: string;
  inkToken: string;
  width: number;
  height: number;
  showEyebrow: boolean;
  showAuthor: boolean;
  showVignette: boolean;
  monogram: boolean;
  monogramText: string;
  authorName: string;
  anonymous: boolean;
  longTitle: boolean;
  shortTitle: boolean;
}

/**
 * Normalize one book's facts into everything the cover renders. The title is
 * trimmed once and feeds every axis — variant included, so stray padding
 * cannot shift the layout. Detail tiers: wizard and hero carry the vignette
 * (unless the title runs long), shelf drops it, mini keeps only the monogram.
 * An absent author stays a visible line (`showAuthor`); `anonymous` tells the
 * component to localize the placeholder instead of a name.
 */
export function coverModel(input: {
  title: string;
  genre?: string | null;
  author?: string | null;
  size: CoverSize;
}): CoverModel {
  const channel = channelFor(input.genre);
  const tokens = CHANNEL_TOKENS[channel];
  const { width, height } = COVER_SIZES[input.size];

  const title = input.title.trim();
  const words = title.split(/\s+/).filter((word) => word.length > 0);
  const authorName = (input.author ?? "").trim();
  const longTitle = title.length > 60;
  const mini = input.size === "mini";
  const vignetteSize = input.size === "wizard" || input.size === "hero";

  return {
    channel,
    variant: variantFor(title),
    groundToken: tokens.ground,
    inkToken: tokens.ink,
    width,
    height,
    showEyebrow: !mini,
    showAuthor: !mini,
    showVignette: vignetteSize && !longTitle,
    monogram: mini,
    monogramText:
      words
        .slice(0, 2)
        // The first code point, not UTF-16 unit, so an astral initial survives.
        .map((word) => Array.from(word)[0].toUpperCase())
        .join("") || "N",
    authorName,
    anonymous: authorName === "",
    longTitle,
    shortTitle: words.length === 1,
  };
}