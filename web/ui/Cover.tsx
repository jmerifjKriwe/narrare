/**
 * The cover: a book object that gives each book a face on the shelf, in
 * the composition the library screen draws (spec §5.4). Which of the four
 * cover tones a book wears is `hash(title) % 4` — a pure function of the
 * title, so a book keeps its cover across renders, reloads and sessions
 * without the database storing one, and two differently named books can
 * land on the same tone without anyone lying. The fourth tone, slate, is
 * the ground the drafts give the area-chat cover (O-2): the same value as
 * the area hue, but worn as its own token — an object surface, not an
 * accent.
 *
 * One composition for all tones, top to bottom: the spine gradient at the
 * left — the hinge a hard-edged book bends on; the top block, eyebrow
 * (genre, else language) over the title in the brand serif's italic voice;
 * the middle, a genre motif drawn in the hand-drawn 16 px stroke language;
 * the foot, the author line. Sepia adds the gold inset frame. The hero
 * adds the amber rule under the eyebrow and, when the caller passes an
 * imprint, a foot row with the imprint slot and the drafted corner motif.
 * The screen won over the umbrella §6.5 prose's old bottom-aligned and
 * centred variants: every ground reads the same way. All of it is CSS: no
 * file, no uploaded art, nothing to export.
 *
 * The lettering is the brand serif, the EB Garamond stack the prose surface
 * reads in, at the draft's two heading steps (grid 21/28, hero 26/34) and
 * the serif's 600. It clamps to three lines and the clamp carries the
 * overflow; the author and imprint are one line, truncated. Forced colours
 * strip the palette, not the object: the title is real text and every
 * decorative layer — spine, frame, motif, rule, corner mark — is its own
 * element carrying no text, so the lettering stays readable by structure,
 * never by colour.
 *
 * The tile is `aria-hidden`: the card that holds it already names the
 * book — its link's accessible name carries the title and the word count
 * (the shelf's answer, pinned where the card is composed) — and a second
 * copy of the title in the accessibility tree would make "open Der Sturm"
 * read twice.
 */

import { Icon, type IconName } from "./icons";

/** The tile's four looks: ground, ink, spine and the accent its motif and
 *  hero rule wear. A cover's ground is an object surface, never an action
 *  token — dark mode is where borrowing `--primary` made the tile read as a
 *  giant button (#590). The spine strength is the tone's own: the darker
 *  the ground, the more black its hinge takes to read. Pale's accent is its
 *  own ink because the drafted amber cannot clear 3:1 on the linen; the
 *  three dark grounds wear `--cover-motif` (measured 3.38:1 at its closest,
 *  see `globals.css`). */
const TONES = [
  {
    name: "pale",
    ground: "bg-cover-pale",
    ink: "text-cover-pale-ink",
    spine: "from-black/20 via-white/20",
    accent: "text-cover-pale-ink",
    rule: "bg-cover-pale-ink",
    frame: false,
  },
  {
    name: "sepia",
    ground: "bg-cover-sepia",
    ink: "text-cover-sepia-ink",
    spine: "from-black/35 via-white/15",
    accent: "text-cover-motif",
    rule: "bg-cover-motif",
    frame: true,
  },
  {
    name: "ink",
    ground: "bg-cover-ink",
    ink: "text-cover-ink-ink",
    spine: "from-black/50 via-white/10",
    accent: "text-cover-motif",
    rule: "bg-cover-motif",
    frame: false,
  },
  {
    name: "slate",
    ground: "bg-cover-slate",
    ink: "text-cover-slate-ink",
    spine: "from-black/40 via-white/10",
    accent: "text-cover-motif",
    rule: "bg-cover-motif",
    frame: false,
  },
] as const;

/** A tone: the quartet's own name, as the shelf speaks it. */
export type CoverTone = (typeof TONES)[number]["name"];

/** FNV-1a, 32 bit: tiny, order-sensitive, identical in every engine — a
 *  title hashes to the same tone in the browser and in the pin test. */
function toneIndex(title: string): number {
  let hash = 0x811c9dc5;
  for (let at = 0; at < title.length; at += 1) {
    hash ^= title.charCodeAt(at);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash % TONES.length;
}

/** The tone a title wears. */
export function coverTone(title: string): CoverTone {
  return TONES[toneIndex(title)].name;
}

/**
 * The genre motifs, in the order a compound label resolves: the specific
 * genre before the broad one, so "Historischer Roman" gets the cloud and
 * "Kriminalroman" the house. The accent is folded away first, so the
 * German and French spellings a catalog may hold match the same words.
 */
const MOTIFS: { pattern: RegExp; glyph: IconName }[] = [
  {
    pattern: /sci[-\s]?fi|science[-\s]?fiction|\bsf\b|raumfahrt|dystop/,
    glyph: "target",
  },
  {
    pattern: /mystery|krimi|kriminal|crime|thriller|detektei|detective|policier|polar|noir/,
    glyph: "house",
  },
  {
    pattern: /histor|geschicht|history|histoire/,
    glyph: "foggy",
  },
  {
    pattern: /literar|literatur|lit[-\s]?fiction|belletristik|\broman\b/,
    glyph: "waves",
  },
];

/** The motif a genre wears; an unknown genre gets the neutral ring. */
function coverMotif(genre: string | null | undefined): IconName {
  const folded = (genre ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
  if (folded === "") return "ring";
  return MOTIFS.find(({ pattern }) => pattern.test(folded))?.glyph ?? "ring";
}

/**
 * The sizes the shelf needs: the list row's thumbnail, the grid card's
 * cover and the hero's. The drafted boxes are the screens' own (shelf.html:
 * w-36 h-52, w-48 h-72), with the asymmetric book edge the screen draws —
 * 2 px on the spine side, 6 px on the card's fore-edge and 8 px on the
 * hero's. The radius ladder's 4/8/12 would round that spine side away from
 * the screen, so geometry stays in px where the drafts measured it. The
 * tiny list thumbnail keeps the same composition at miniature steps.
 */
const SIZES = {
  md: {
    box: "w-20 aspect-[3/4]",
    radius: "rounded-[var(--radius)]",
    padding: "p-1.5",
    spine: "w-[5px]",
    title: "text-label leading-tight",
    clamp: "line-clamp-2",
    motif: 16,
  },
  card: {
    box: "w-36 h-52",
    radius: "rounded-l-[2px] rounded-r-[6px]",
    padding: "p-3.5",
    spine: "w-2.5",
    title: "text-[1.3125rem] leading-[1.75rem]",
    clamp: "line-clamp-3",
    motif: 40,
  },
  hero: {
    box: "w-48 h-72",
    radius: "rounded-l-[2px] rounded-r-[8px]",
    padding: "p-5",
    spine: "w-3.5",
    title: "text-[1.625rem] leading-[2.125rem]",
    clamp: "line-clamp-3",
    motif: 72,
  },
} as const;

export type CoverSize = keyof typeof SIZES;

export function Cover({
  title,
  size = "md",
  genre = null,
  language = null,
  author,
  imprint,
}: {
  title: string;
  size?: CoverSize;
  genre?: string | null;
  language?: string | null;
  /** The book's author. Omitted: no foot line. Null: a real absence, "—". */
  author?: string | null;
  /** The imprint slot. Omitted: no row. Present: the text, or "—" for null. */
  imprint?: string | null;
}) {
  const look = TONES[toneIndex(title)];
  const box = SIZES[size];
  const motif = coverMotif(genre);
  // The eyebrow is the book's one catalogued fact: a genre, or the language
  // it is written in. No counts — the card already carries them. An empty
  // genre is no genre: the language answers instead.
  const eyebrow = genre?.trim() ? genre : (language?.toUpperCase() ?? "");
  const authorLine = author?.trim() ? author : "—";
  // The imprint is interim: no novel field carries one yet, so the drafted
  // slot holds its geometry with the neutral value until it does (#832).
  const imprintLine = imprint?.trim() ? imprint : "—";
  return (
    <div
      aria-hidden="true"
      data-cover-tone={look.name}
      className={`relative flex shrink-0 flex-col justify-between overflow-hidden ${box.box} ${box.radius} ${box.padding} ${
        size === "hero" ? "shadow-2xl" : "shadow-lg"
      } ${look.ground} ${look.ink}`}
    >
      {/* The spine: the drafted gradient, 2.5 units wide on the grid cover
       * and 3.5 on the hero. Its strength is the tone's own — a uniform one
       * is invisible on the midnight ground, and the tone's ink is no
       * substitute: it would lighten the dark grounds it has to shade.
       * Decorative: it carries no text and no forced palette needs it. */}
      <span
        data-cover-spine
        className={`pointer-events-none absolute inset-y-0 left-0 ${box.spine} bg-gradient-to-r ${look.spine} to-transparent`}
      />
      {look.frame ? (
        /* Sepia's gold frame: a 1 px hairline at a 5 px offset. No token
         * names a gold; the tone's own ink washed at 35 % over the
         * terracotta is the warm gold the drafts mean, and it stays the
         * ink's tint so the frame follows the theme with its ground. */
        <span
          data-cover-frame
          className="pointer-events-none absolute inset-[5px] rounded-[2px] border border-current opacity-35"
        />
      ) : null}
      <div data-cover-top className="relative z-10 flex w-full min-w-0 flex-col items-start">
        {eyebrow !== "" ? (
          <span
            data-cover-eyebrow
            /* The design's micro-label step, at 80 %: measured on every
             * ground it rides — 8.03:1 on pale light, 6.00:1 on sepia
             * light, 4.60:1 on slate light (the closest), 7.08:1 / 7.42:1 /
             * 6.89:1 on the dark half's grounds. One line: a long genre
             * must not wrap over the title below it. */
            className="w-full truncate text-eyebrow uppercase opacity-80"
          >
            {eyebrow}
          </span>
        ) : null}
        {size === "hero" ? (
          /* The hero's amber rule, drawn at full strength rather than the
           * draft's 80 %: the accent already sits at 3.38:1 on the light
           * slate ground, and the wash would drop it under the 3:1 a
           * graphic needs. */
          <span
            data-cover-rule
            aria-hidden="true"
            className={`mt-1.5 mb-2.5 h-0.5 w-6 shrink-0 ${look.rule}`}
          />
        ) : null}
        <span
          data-cover-title
          /* The draft's two heading steps: the grid's prose-heading-2
           * (21 / 28) and the hero's prose-heading-1 (26 / 34), in the
           * serif's italic 600. The clamp carries the overflow. */
          className={`w-full break-normal hyphens-none overflow-hidden text-left font-garamond font-semibold italic ${box.clamp} ${box.title}`}
        >
          {title}
        </span>
      </div>
      <div
        data-cover-motif={motif}
        aria-hidden="true"
        /* The glyph sits at the tone's accent ink, full strength: the
         * drafts' 60–70 % wash would leave the amber at 2.6:1 on the light
         * slate ground, under the 3:1 a graphic needs. */
        className={`relative z-10 self-center ${look.accent}`}
      >
        <Icon name={motif} size={box.motif} />
      </div>
      <div className="relative z-10 flex w-full min-w-0 flex-col gap-0.5">
        {author !== undefined ? (
          <span
            data-cover-author
            /* The author follows the eyebrow's measured wash (80 % of the
             * tone ink); real data already exists, so only a null author
             * needs the placeholder. An omitted prop means this caller
             * carries no author line, not that the book has none. */
            className="w-full truncate text-meta opacity-80"
          >
            {authorLine}
          </span>
        ) : null}
        {size === "hero" && imprint !== undefined ? (
          <div
            data-cover-imprint
            className="flex w-full min-w-0 items-center justify-between gap-2"
          >
            <span className="min-w-0 truncate text-meta opacity-80">{imprintLine}</span>
            {/* The drafted foot row's corner mark is decoration: the genre
             * is already named in the eyebrow, so the glyph is hidden from
             * the tree with the rest of the tile. */}
            <span
              data-cover-corner
              aria-hidden="true"
              className={`shrink-0 ${look.accent}`}
            >
              <Icon name="radar" size={16} />
            </span>
          </div>
        ) : null}
      </div>
    </div>
  );
}
