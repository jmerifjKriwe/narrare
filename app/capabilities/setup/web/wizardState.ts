import { useNavigate, useSearch } from "@tanstack/react-router";
import { useCallback, useMemo } from "react";

import { demos } from "@shell/lib/generated/demos";

/**
 * The wizard's accumulated answers, held in the address — not in a store and
 * not on the server. Every step reads and writes the same search params, so a
 * refresh mid-wizard lands on the same step with the same answers (Task 3's
 * `/setup` redirect keeps the search on purpose), and nothing is posted until
 * step 4. This module is the one typed seam over those params: a pure
 * read/serialize pair the steps share, plus the genre-join rule the backend
 * contract binds (`genre` is a single string, ≤80 chars, the pills joined with
 * ", "). No server writes live here.
 *
 * The parse is defensive on purpose: a hand-edited or stale address must never
 * inject an unknown demo, an unknown genre, or an out-of-range number into the
 * one POST the wizard makes. Unknown values fall to the honest default, never
 * to a crash.
 */

/** The backend's per-novel vocabularies (setup/schemas.py), shared by the steps. */
export type Typology = "plotter" | "pantser" | "plantser";
export type AiRole = "archivar" | "coautor" | "lektor" | "sparring";
export const DRAMATIC_FORMS = [
  "three-act",
  "heros-journey",
  "save-the-cat",
  "five-act",
  "seven-point",
] as const;
export type DramaticForm = (typeof DRAMATIC_FORMS)[number];

export interface WizardState {
  title: string;
  genrePills: string[];
  targetWords: number;
  typology: Typology | null;
  form: DramaticForm | null;
  aiRole: AiRole | null;
  canon: number | null;
  demo: string | null;
}

/**
 * The five genre pills, in the draft's order. The `value` is the canonical
 * label the draft speaks and the one the backend receives and the cover system
 * recognizes (cover.ts's CHANNEL_ALIASES carries exactly these five); the
 * visible face is localized through the catalog key, so the joined string a
 * reader sends never depends on the language they read the UI in.
 */
export const GENRE_PILL_DEFS = [
  { value: "Science Fiction & Speculative", key: "setup.basis.genre.scifi" },
  { value: "Mystery & Noir", key: "setup.basis.genre.mystery" },
  { value: "Historischer Roman", key: "setup.basis.genre.historical" },
  { value: "Literarische Belletristik", key: "setup.basis.genre.literary" },
  { value: "Low Fantasy / Magischer Realismus", key: "setup.basis.genre.lowfantasy" },
] as const;

export const GENRE_PILLS: readonly string[] = GENRE_PILL_DEFS.map((pill) => pill.value);

/** The backend's `genre` ceiling (setup/schemas.py): the joined string's cap. */
export const GENRE_CAP = 80;

/** The draft's default target and the Integer column's own ceiling. */
export const DEFAULT_TARGET_WORDS = 65_000;
export const TARGET_WORDS_MAX = 2_147_483_647;

const TYPOLOGIES: readonly Typology[] = ["plotter", "pantser", "plantser"];
const AI_ROLES: readonly AiRole[] = ["archivar", "coautor", "lektor", "sparring"];
const DEMO_SLUGS: readonly string[] = demos.map((demo) => demo.slug);

/** The one string the backend receives: the selected pills, joined ", ". */
export function joinGenres(pills: readonly string[]): string {
  return pills.join(", ");
}

/** Whether adding `pill` to the selection would overflow the 80-char cap. A
 *  pill already selected is never an "add" — removing it is always allowed. */
export function wouldOverflow(pills: readonly string[], pill: string): boolean {
  if (pills.includes(pill)) return false;
  return joinGenres([...pills, pill]).length > GENRE_CAP;
}

/** The demo a slug names, or null — the one lookup the steps share. */
export function findDemo(slug: string | null) {
  return demos.find((demo) => demo.slug === slug) ?? null;
}

/** Step 1 is complete iff a demo is chosen or a working title stands. */
export function basisComplete(state: WizardState): boolean {
  return state.demo !== null || state.title.trim() !== "";
}

/** An integer from a search value, or null — never a NaN into the state. */
function toInt(value: unknown): number | null {
  if (typeof value === "number" && Number.isInteger(value)) return value;
  if (typeof value === "string" && /^\d+$/.test(value.trim())) return Number(value.trim());
  return null;
}

function oneOf<T extends string>(value: unknown, allowed: readonly T[]): T | null {
  return typeof value === "string" && (allowed as readonly string[]).includes(value)
    ? (value as T)
    : null;
}

/**
 * The pure read: search params → the typed answers, with honest defaults. The
 * genre list keeps only known pills, dedupes, and honors the cap in order, so
 * even a hand-edited address cannot carry an over-cap genre into the POST.
 */
export function readWizardState(search: Record<string, unknown>): WizardState {
  const rawGenres = search.genres;
  const parts =
    typeof rawGenres === "string"
      ? rawGenres.split(",")
      : Array.isArray(rawGenres)
        ? rawGenres.map(String)
        : [];
  const genrePills: string[] = [];
  for (const part of parts) {
    const pill = part.trim();
    if (!GENRE_PILLS.includes(pill) || genrePills.includes(pill)) continue;
    if (wouldOverflow(genrePills, pill)) continue;
    genrePills.push(pill);
  }

  const words = toInt(search.words);
  const canon = toInt(search.canon);

  return {
    title: typeof search.title === "string" ? search.title : "",
    genrePills,
    targetWords:
      words !== null && words >= 1 && words <= TARGET_WORDS_MAX ? words : DEFAULT_TARGET_WORDS,
    typology: oneOf(search.typology, TYPOLOGIES),
    form: oneOf(search.form, DRAMATIC_FORMS),
    aiRole: oneOf(search.role, AI_ROLES),
    canon: canon !== null && canon >= 1 && canon <= 5 ? canon : null,
    demo: oneOf(search.demo, DEMO_SLUGS),
  };
}

/**
 * The pure write: the typed answers → search params. Defaults and empty
 * answers serialize to `undefined`, which the router drops, so the address
 * stays clean and a cleared field truly clears its param. Non-wizard params
 * are preserved by the caller's spread.
 */
export function wizardSearch(state: WizardState): Record<string, string | number | undefined> {
  return {
    title: state.title.trim() === "" ? undefined : state.title,
    genres: state.genrePills.length > 0 ? state.genrePills.join(",") : undefined,
    words: state.targetWords === DEFAULT_TARGET_WORDS ? undefined : state.targetWords,
    typology: state.typology ?? undefined,
    form: state.form ?? undefined,
    role: state.aiRole ?? undefined,
    canon: state.canon ?? undefined,
    demo: state.demo ?? undefined,
  };
}

/**
 * The hook each step uses: the typed answers plus an `update` that merges a
 * patch into the address. `replace` keeps a keystroke from stacking a history
 * entry — the refinements are one step, the step-to-step moves are the pushes.
 *
 * The merge reads the router's latest search inside the functional updater,
 * never a render closure: two refinements in one tick (a keystroke and a
 * click) compose instead of the second clobbering the first. A patch may be
 * a value or a function of the current answers — the pill toggle uses the
 * function form so rapid selections compose the same way.
 */
export type WizardPatch =
  | Partial<WizardState>
  | ((prev: WizardState) => Partial<WizardState>);

/** The wizard's own step paths — each step passes its own, so the typed
 *  navigate below resolves its search reducer against a real route (an
 *  unbound `useNavigate()` degrades the reducer's type to `never`). The
 *  update carries no `to`, so it stays on the step it was called from. */
export type WizardStepPath =
  | "/setup/basis"
  | "/setup/structure"
  | "/setup/ai-rules"
  | "/setup/provisioning";

export function useWizardState(from: WizardStepPath): {
  state: WizardState;
  update: (patch: WizardPatch) => void;
} {
  const search = useSearch({ strict: false }) as Record<string, unknown>;
  const navigate = useNavigate({ from });
  const state = useMemo(() => readWizardState(search), [search]);
  const update = useCallback(
    (patch: WizardPatch) => {
      void navigate({
        search: (prev) => {
          const current = readWizardState(prev);
          const next = { ...current, ...(typeof patch === "function" ? patch(current) : patch) };
          return { ...prev, ...wizardSearch(next) };
        },
        replace: true,
      });
    },
    [navigate],
  );
  return { state, update };
}
