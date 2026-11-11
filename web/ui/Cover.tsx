/**
 * The cover: a 3:4 book object that gives each book a face on the shelf.
 * Which of the four cover tones a book wears is `hash(title) % 4` — a pure
 * function of the title, so a book keeps its cover across renders, reloads
 * and sessions without the database storing one, and two differently named
 * books can land on the same tone without anyone lying. The fourth tone,
 * slate, is the ground the drafts give the area-chat cover (O-2): the same
 * value as the area hue, but worn as its own token — an object surface,
 * not an accent.
 *
 * A tone is more than a ground; the quartet is four composed objects, not
 * four fills. Every tone carries the spine: 5 px of the ground darkened,
 * the hinge a hard-edged book bends on. The three foot-tones set their
 * title at the foot in the brand serif, and the corner eyebrow above it —
 * pale's named mark in the norm — names the book's genre or its language;
 * sepia adds the gold frame. Ink is the drafted midnight object: its title
 * centres, and its metadata follows beneath it at 60 %. All of it is CSS:
 * no file, no uploaded art, nothing to export.
 *
 * The lettering is the brand serif, the EB Garamond stack the prose
 * surface reads in, at the weight the serif's headings carry; it clamps to
 * three lines, and the clamp carries the overflow. Forced colours strip
 * the palette, not the object: the title is real text and every
 * decorative layer — spine, frame, eyebrow — is its own empty span, so
 * the lettering stays readable by structure, never by colour.
 *
 * The tile is `aria-hidden`: the card that holds it already names the
 * book — its link's accessible name carries the title and the word count
 * (the shelf's answer, pinned where the card is composed) — and a second
 * copy of the title in the accessibility tree would make "open Der Sturm"
 * read twice.
 */

/** The tile's four looks: ground, ink, and the composition each tone owns.
 *  A cover's ground is an object surface, never an action token — dark mode
 *  is where borrowing `--primary` made the tile read as a giant button
 *  (#590). The spine strength is the ground's own: the darker the ground,
 *  the more black its hinge takes to read. */
const TONES = [
  { name: "pale", ground: "bg-cover-pale", ink: "text-cover-pale-ink", spine: "bg-black/20", frame: false, centered: false },
  { name: "sepia", ground: "bg-cover-sepia", ink: "text-cover-sepia-ink", spine: "bg-black/40", frame: true, centered: false },
  { name: "ink", ground: "bg-cover-ink", ink: "text-cover-ink-ink", spine: "bg-black/60", frame: false, centered: true },
  { name: "slate", ground: "bg-cover-slate", ink: "text-cover-slate-ink", spine: "bg-black/40", frame: false, centered: false },
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

/** The two widths the shelf needs: the card's thumbnail and the hero's. */
const SIZES = {
  md: "w-20",
  lg: "w-28",
} as const;

export type CoverSize = keyof typeof SIZES;

export function Cover({
  title,
  size = "md",
  genre = null,
  language = null,
}: {
  title: string;
  size?: CoverSize;
  genre?: string | null;
  language?: string | null;
}) {
  const look = TONES[toneIndex(title)];
  // The eyebrow is the book's one catalogued fact: a genre, or the language
  // it is written in. No counts — the card already carries them. An empty
  // genre is no genre: the language answers instead.
  const eyebrow = genre?.trim() ? genre : (language?.toUpperCase() ?? "");
  return (
    <div
      aria-hidden="true"
      data-cover-tone={look.name}
      className={`relative flex ${look.centered ? "flex-col items-center justify-center" : "items-end"} shrink-0 ${SIZES[size]} aspect-[3/4] overflow-hidden rounded-[var(--radius)] border border-border p-1.5 ${
        look.ground
      } ${look.ink}`}
    >
      {/* The spine: 5 px of the ground darkened, the one strip every tone
       * bends on. The strengths come from the rendered composition, which
       * names them per tone — pale 20 %, sepia 40 %, slate 40 %, ink 60 %
       * (the dark shelf names all four; the light shelf agrees on pale):
       * a uniform strength is invisible on the midnight ground, and the
       * tone's ink is no substitute — it would lighten the dark grounds it
       * has to shade. Decorative: it carries no text and no forced palette
       * needs it. */}
      <span
        data-cover-spine
        className={`pointer-events-none absolute inset-y-0 left-0 w-[5px] ${look.spine}`}
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
      {!look.centered && eyebrow !== "" ? (
        <span
          data-cover-eyebrow
          /* The design's micro-label step, at 80 %: measured on every
           * ground it rides — 8.03:1 on pale light, 6.00:1 on sepia light,
           * 4.60:1 on slate light (the closest), 7.08:1 / 7.42:1 / 6.89:1
           * on the dark half's grounds. One line: a long genre must not
           * wrap over the title below it. */
          className="absolute left-1.5 right-1.5 top-1.5 truncate text-eyebrow uppercase opacity-80"
        >
          {eyebrow}
        </span>
      ) : null}
      <span
        className={`line-clamp-3 w-full overflow-hidden break-words font-semibold text-label leading-tight [font-family:'EB_Garamond',Georgia,'Times_New_Roman',serif] ${
          look.centered ? "text-center" : "text-left"
        }`}
      >
        {title}
      </span>
      {look.centered && eyebrow !== "" ? (
        <span
          data-cover-eyebrow
          /* Ink's metadata follows its centred title at 60 %, as the drafts
           * draw the midnight object: measured 6.33:1 on the light ground
           * and 5.55:1 on the dark one. */
          className="mt-0.5 w-full truncate text-center text-eyebrow uppercase opacity-60"
        >
          {eyebrow}
        </span>
      ) : null}
    </div>
  );
}
