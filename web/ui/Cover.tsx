/**
 * The cover: a 3:4 tile that gives each book a face on the shelf. Which of
 * the three cover tones a book wears is `hash(title) % 3` — a pure function
 * of the title, so a book keeps its cover across renders, reloads and
 * sessions without the database storing one, and two differently named
 * books can land on the same tone without anyone lying.
 *
 * A tone is more than a ground. Pale and sepia set the title at the foot and
 * name the book's genre (or its language) in the corner; sepia adds an inset
 * hairline and a spine strip, so the three tiles are three objects rather
 * than three fills. Ink centres its title. All of it is CSS: no file, no
 * uploaded art, nothing to export.
 *
 * The tile is `aria-hidden`: the card that holds it already names the book
 * (the card link's accessible name is the shelf's answer), and a second
 * copy of the title in the accessibility tree would make "open Der Sturm"
 * read twice. The lettering is the brand serif, the EB Garamond stack the
 * prose surface reads in; it clamps to three lines, and the clamp carries
 * the overflow.
 */

/** The tile's three looks: ground, ink, and the composition each tone owns.
 *  A cover's ground is an object surface, never an action token — dark mode
 *  is where borrowing `--primary` made the tile read as a giant button
 *  (#590). */
const TONES = [
  { name: "pale", ground: "bg-cover-pale", ink: "text-cover-pale-ink", frame: false, centered: false },
  { name: "sepia", ground: "bg-cover-sepia", ink: "text-cover-sepia-ink", frame: true, centered: false },
  { name: "ink", ground: "bg-cover-ink", ink: "text-cover-ink-ink", frame: false, centered: true },
] as const;

/** A tone: an index into `TONES`. */
export type CoverTone = 0 | 1 | 2;

/** FNV-1a, 32 bit: tiny, order-sensitive, identical in every engine — a
 *  title hashes to the same tone in the browser and in the pin test. */
export function coverTone(title: string): CoverTone {
  let hash = 0x811c9dc5;
  for (let at = 0; at < title.length; at += 1) {
    hash ^= title.charCodeAt(at);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return (hash % 3) as CoverTone;
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
  const look = TONES[coverTone(title)];
  // The eyebrow is the book's one catalogued fact: a genre, or the language
  // it is written in. No counts — the card already carries them. An empty
  // genre is no genre: the language answers instead.
  const eyebrow = genre?.trim() ? genre : (language?.toUpperCase() ?? "");
  return (
    <div
      aria-hidden="true"
      data-cover-tone={look.name}
      className={`relative flex shrink-0 ${SIZES[size]} aspect-[3/4] overflow-hidden rounded-[var(--radius)] border border-border p-1.5 ${
        look.ground
      } ${look.ink} ${look.centered ? "items-center justify-center" : "items-end"}`}
    >
      {look.frame ? (
        <>
          <span
            data-cover-frame
            className="pointer-events-none absolute inset-[5px] rounded-[2px] border border-current opacity-35"
          />
          <span className="pointer-events-none absolute inset-y-0 left-0 w-[5px] bg-current opacity-20" />
        </>
      ) : null}
      {eyebrow === "" ? null : (
        <span
          data-cover-eyebrow
          /* 8 px is deliberately off the UI scale: this is a spine caption on
           * an object, not UI text, and the census only sees the named scale
           * steps. 0.8, not 0.7: at 0.7 the dark sepia pair measured 4.30:1,
           * under AA; 0.8 measures 5.12:1. */
          className="absolute left-1.5 right-1.5 top-1.5 truncate text-[8px] uppercase tracking-[0.08em] opacity-80"
        >
          {eyebrow}
        </span>
      )}
      <span
        className={`line-clamp-3 w-full overflow-hidden break-words text-label leading-tight [font-family:'EB_Garamond',Georgia,'Times_New_Roman',serif] ${
          look.centered ? "text-center" : "text-left"
        }`}
      >
        {title}
      </span>
    </div>
  );
}
