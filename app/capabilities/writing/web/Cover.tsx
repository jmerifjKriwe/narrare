/**
 * The cover: a 3:4 tile that gives each book a face on the shelf. Which of
 * the three token tones a book wears is `hash(title) % 3` — a pure function
 * of the title, so a book keeps its cover across renders, reloads and
 * sessions without the database storing one, and two differently named
 * books can land on the same tone without anyone lying. The lettering is
 * the brand serif, the EB Garamond stack the prose surface reads in
 * (`.ProseMirror`'s `@font-face`); it clamps to three lines, and the clamp
 * carries the overflow so a long title paints inside the tile and nowhere
 * else.
 *
 * The tile is `aria-hidden`: the card that holds it already names the book
 * (the card link's accessible name is the shelf's answer), and a second
 * copy of the title in the accessibility tree would make "open Der Sturm"
 * read twice. The one call this wave makes — shelf card and hero — both
 * name the book; a standalone cover that must speak would drop this
 * attribute at its own call site, with the reasoning above.
 */

/** The tile's three looks, all token-derived: the quiet wash, the brand
 *  hue at a breath, and the brand fill. Ink pairs with the fill — text
 *  muted never sits on a fill here (the parked AA rule). */
export const COVER_TONES = [
  "bg-soft text-foreground",
  "bg-primary/20 text-foreground",
  "bg-primary text-primary-foreground",
] as const;

/** A tone: an index into `COVER_TONES`. */
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

export function Cover({ title, size = "md" }: { title: string; size?: CoverSize }) {
  return (
    <div
      aria-hidden="true"
      className={`flex shrink-0 ${SIZES[size]} aspect-[3/4] items-stretch rounded-[var(--radius)] border border-border p-1.5 ${
        COVER_TONES[coverTone(title)]
      }`}
    >
      <span className="line-clamp-3 w-full self-center overflow-hidden text-center [font-family:'EB_Garamond',Georgia,'Times_New_Roman',serif] text-label leading-tight">
        {title}
      </span>
    </div>
  );
}
