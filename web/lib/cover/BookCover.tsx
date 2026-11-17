/**
 * The procedural book object — the presentational cover the setup wizard's
 * live preview and the shelf both wear. Pure CSS/SVG, no imagery: the model
 * (cover.ts) decides the channel, the variant axis and the detail tier; this
 * component ports the archived Stitch spec (docs/design/stitch/screens/
 * library/cover-system.html) onto the shell's tokens.
 *
 * Anatomy (Sektion 01, 267–299): a spine-crease gradient down the bound left
 * edge, a blind-deboss inner boundary, a tracked genre eyebrow over a hairline
 * rule, the hairline genre vignette (Task 4's GenreMotif) receding behind the
 * title, the title in EB Garamond italic, and the author line. The left edge is
 * square (the thread-sewn spine), the right softly rounded — a book, not a card.
 *
 * Three compositions, not one layout relabeled (R10, Sektion 03, 597–684):
 *   0  centered classic — everything rests on the optical center;
 *   1  offset axis — the vignette shifts off the spine, the type stays left;
 *   2  monumental whitespace — a small edge vignette beside the eyebrow, the
 *      title owns the middle, the author sits under a rule at the foot.
 * The title hash spreads same-genre books over the three, so a shelf never
 * reads as duplicates.
 *
 * Ground/ink ride LITERAL Tailwind utilities (R2): Tailwind v4 only emits the
 * classes it sees verbatim, so the palette is a static record of `bg-cover-*`
 * and `text-cover-*-ink` names — never a concatenation, never an inline var().
 * The dimmed text roles (eyebrow, author, variant-2 foot) ride the same
 * literal discipline: they keep the spec's opacity wherever it clears WCAG AA
 * and rise per channel only where it would not (R15, owner decision). The
 * fractions live in cover.ts's COVER_TEXT_DIMS, the utilities below render
 * them, and the token gate measures the composite the reader actually sees.
 *
 * Dark mode keeps the pigment (R9, Sektion 06): a book is a material object and
 * is never inverted. It gains only a uniform 1px white-8% rim on three sides and
 * a deeper contact shadow. Both ride `light-dark()`, the shell's own theme
 * mechanism (color-scheme), so a reader's forced light or dark choice is honored
 * exactly — a `prefers-color-scheme` media query would outrun a forced theme.
 * The two tactile shadows and the two crease gradients below are the spec's CSS
 * (147–178) ported verbatim into arbitrary utilities.
 *
 * The edges (Sektion 05) never break the layout: a long title clamps to three
 * lines with no ellipsis and lets the vignette recede; a single mammoth word
 * breaks rather than overflows; an absent author keeps a localized "Anonymus"
 * line; an unknown genre falls to the neutral linen with the atelier seal; the
 * miniature keeps only the monogram inside its 36×48 box.
 */

import type { ReactElement } from "react";

import { useTranslation, type MessageKey } from "../i18n";
import { coverModel, type CoverChannel, type CoverSize } from "./cover";
import { GenreMotif } from "./motifs";

/** R2: the literal ground/ink utilities per channel — the scanner sees each.
 * These literals render the model's groundToken/inkToken (CHANNEL_TOKENS in
 * cover.ts); R2 requires literals, so the token names are advisory here and
 * the palette-pin test in BookCover.test.tsx keeps the two in sync. Exported
 * for the chrome's cover chip (W4 Task 10): the rail's book switcher wears
 * the cover system's pigment at chip size, from this one literal record. */
export const PALETTE: Record<CoverChannel, { ground: string; ink: string }> = {
  scifi: { ground: "bg-cover-ink", ink: "text-cover-ink-ink" },
  fantasy: { ground: "bg-cover-fantasy", ink: "text-cover-fantasy-ink" },
  mystery: { ground: "bg-cover-pale", ink: "text-cover-pale-ink" },
  literary: { ground: "bg-cover-sepia", ink: "text-cover-sepia-ink" },
  historical: { ground: "bg-cover-slate", ink: "text-cover-slate-ink" },
  romance: { ground: "bg-cover-romance", ink: "text-cover-romance-ink" },
  thriller: { ground: "bg-cover-thriller", ink: "text-cover-thriller-ink" },
  fallback: { ground: "bg-cover-fallback", ink: "text-cover-fallback-ink" },
};

/** R2/R15: the literal opacity utilities per channel and text role — the
 * scanner sees each. These are the class-name half of COVER_TEXT_DIMS in
 * cover.ts (the numeric half the contrast gate measures); the dim-pin test
 * below keeps the two in sync. Raised above the spec dim only where AA
 * demands it: historical on every role, four channels' variant-2 feet. */
const TEXT_OPACITY: Record<
  CoverChannel,
  { eyebrow: string; author: Record<Exclude<CoverSize, "mini">, string>; foot: string }
> = {
  scifi: {
    eyebrow: "opacity-70",
    author: { wizard: "opacity-75", hero: "opacity-75", shelf: "opacity-70" },
    foot: "opacity-60",
  },
  fantasy: {
    eyebrow: "opacity-70",
    author: { wizard: "opacity-75", hero: "opacity-75", shelf: "opacity-70" },
    foot: "opacity-60",
  },
  mystery: {
    eyebrow: "opacity-70",
    author: { wizard: "opacity-75", hero: "opacity-75", shelf: "opacity-70" },
    foot: "opacity-65",
  },
  literary: {
    eyebrow: "opacity-70",
    author: { wizard: "opacity-75", hero: "opacity-75", shelf: "opacity-70" },
    foot: "opacity-65",
  },
  historical: {
    eyebrow: "opacity-80",
    author: { wizard: "opacity-80", hero: "opacity-80", shelf: "opacity-80" },
    foot: "opacity-80",
  },
  romance: {
    eyebrow: "opacity-70",
    author: { wizard: "opacity-75", hero: "opacity-75", shelf: "opacity-70" },
    foot: "opacity-65",
  },
  thriller: {
    eyebrow: "opacity-70",
    author: { wizard: "opacity-75", hero: "opacity-75", shelf: "opacity-70" },
    foot: "opacity-60",
  },
  fallback: {
    eyebrow: "opacity-70",
    author: { wizard: "opacity-75", hero: "opacity-75", shelf: "opacity-70" },
    foot: "opacity-65",
  },
};

/** The eyebrow's localized genre label, keyed literally for the typed `t`. */
const GENRE_KEYS: Record<CoverChannel, MessageKey> = {
  scifi: "cover.genre.scifi",
  fantasy: "cover.genre.fantasy",
  mystery: "cover.genre.mystery",
  literary: "cover.genre.literary",
  historical: "cover.genre.historical",
  romance: "cover.genre.romance",
  thriller: "cover.genre.thriller",
  fallback: "cover.genre.fallback",
};

/** The brand serif, the cover title's voice — the shell's one serif token
 * (globals.css `--font-serif`, R17), the same stack the prose surface reads. */
const SERIF = "[font-family:var(--font-serif)]";

/**
 * The spine crease (spec 147–164), verbatim. The pale grounds — mystery's
 * Steinpergament and the fallback linen — take the warm pale crease; every
 * dark ground takes the black one (the specimens: sepia→black, pale→pale,
 * ink→black).
 */
const CREASE =
  "bg-[linear-gradient(90deg,rgba(0,0,0,0.28)_0%,rgba(0,0,0,0.12)_3%,rgba(255,255,255,0.25)_5%,rgba(0,0,0,0.08)_8%,transparent_14%)]";
const CREASE_PALE =
  "bg-[linear-gradient(90deg,rgba(44,24,16,0.2)_0%,rgba(44,24,16,0.08)_3%,rgba(255,255,255,0.6)_5%,rgba(44,24,16,0.05)_8%,transparent_14%)]";

/**
 * The uniform dark rim (R9, Sektion 06 prose): 1px of rgba(255,255,255,0.08)
 * on the top, right and bottom — never the spine side — transparent in the
 * light half. The widths ride plain utilities; only the color switches.
 */
const RIM = "border-t border-r border-b [border-color:light-dark(transparent,rgba(255,255,255,0.08))]";

/**
 * The two tactile shadows (spec 165–178), verbatim, one layer per light-dark()
 * pair: the light half's warm ink wash, the dark half's deeper contact shadow.
 * The arbitrary-property form is deliberate: a shadow utility with an arbitrary
 * light-dark() value would misread it as a shadow *color*, since light-dark()
 * is a color function.
 */
const SHADOW =
  "[box-shadow:light-dark(0_1px_2px_rgba(44,24,16,0.06),0_2px_4px_rgba(0,0,0,0.6)),light-dark(0_4px_12px_rgba(44,24,16,0.08),0_8px_24px_rgba(0,0,0,0.45)),light-dark(inset_1px_0_0_rgba(255,255,255,0.15),inset_1px_0_0_rgba(255,255,255,0.08)),light-dark(inset_-1px_0_0_rgba(0,0,0,0.1),inset_-1px_0_0_rgba(0,0,0,0.4))]";

/** Per-size typography and ornament scale (Sektion 04, 685–780). The miniature
 * reads only padding, creaseWidth, pad and rightRadius — it keeps the monogram
 * alone. The right radius scales with the book (R13): 6/5/4/2px down the
 * matrix, the spine side stays square at every size. */
interface SizeMetrics {
  padding: string;
  creaseWidth: string;
  pad: string;
  rightRadius: string;
  eyebrow: string;
  title: string;
  titleMonumental: string;
  titleShort: string;
  titleLong: string;
  /** The normal title's leading plus its three-line clamp (max-height = 3 ×
   * the leading): tight at wizard/hero (spec 713/736), snug at shelf (753). */
  titleClamp: string;
  /** The title block's spacing: wizard space-y-1 (spec 712), hero and shelf
   * space-y-0.5 (spec 735/752). */
  titleSpacing: string;
  author: string;
  motif: string;
  motifEdge: string;
}

const METRICS: Record<CoverSize, SizeMetrics> = {
  wizard: {
    padding: "p-5",
    creaseWidth: "w-3",
    pad: "pl-2",
    rightRadius: "rounded-r-[6px]",
    eyebrow: "text-[9px] tracking-widest",
    title: "text-[21px]",
    titleMonumental: "text-[24px]",
    titleShort: "text-[28px]",
    titleLong: "text-[15px]",
    titleClamp: "leading-tight max-h-[3.75em]", // spec 713
    titleSpacing: "space-y-1", // spec 712
    author: "text-[11px]",
    motif: "size-14",
    motifEdge: "size-8",
  },
  hero: {
    padding: "p-4",
    creaseWidth: "w-2.5",
    pad: "pl-1.5",
    rightRadius: "rounded-r-[5px]",
    eyebrow: "text-[8px] tracking-widest",
    title: "text-[18px]",
    titleMonumental: "text-[20px]",
    titleShort: "text-[24px]",
    titleLong: "text-[14px]",
    titleClamp: "leading-tight max-h-[3.75em]", // spec 736
    titleSpacing: "space-y-0.5", // spec 735
    author: "text-[10px]",
    motif: "size-10",
    motifEdge: "size-6",
  },
  shelf: {
    padding: "p-3",
    creaseWidth: "w-2",
    pad: "pl-1",
    rightRadius: "rounded-r-[4px]",
    eyebrow: "text-[7px] tracking-wider",
    title: "text-[14px]",
    titleMonumental: "text-[16px]",
    titleShort: "text-[18px]",
    titleLong: "text-[12px]",
    titleClamp: "leading-snug max-h-[4.125em]", // spec 753; the clamp tracks the leading
    titleSpacing: "space-y-0.5", // spec 752
    author: "text-[9px]",
    motif: "size-8",
    motifEdge: "size-5",
  },
  mini: {
    padding: "p-1",
    creaseWidth: "w-1",
    pad: "pl-0.5",
    rightRadius: "rounded-r-[2px]",
    eyebrow: "text-[6px] tracking-wider",
    title: "text-[9px]",
    titleMonumental: "text-[9px]",
    titleShort: "text-[9px]",
    titleLong: "text-[9px]",
    titleClamp: "leading-tight max-h-[3.75em]",
    titleSpacing: "space-y-0.5",
    author: "text-[6px]",
    motif: "size-4",
    motifEdge: "size-3",
  },
};

function cx(...parts: Array<string | false | undefined>): string {
  return parts.filter((part): part is string => Boolean(part)).join(" ");
}

export function BookCover({
  title,
  genre,
  author,
  size = "shelf",
  className,
}: {
  title: string;
  genre?: string | null;
  author?: string | null;
  size?: CoverSize;
  className?: string;
}): ReactElement {
  const t = useTranslation();
  const model = coverModel({ title, genre, author, size });
  const m = METRICS[size];
  const palette = PALETTE[model.channel];
  const dims = TEXT_OPACITY[model.channel];
  // The two light grounds (Sektion 02 specimens): mystery's Steinpergament
  // and the fallback linen take the warm pale crease and the quieter motif;
  // every dark ground takes the black crease.
  const lightGround = model.channel === "mystery" || model.channel === "fallback";
  const titleText = title.trim();
  const authorText = model.anonymous ? t("cover.anonymous") : model.authorName;

  // A long title takes the small three-line rhythm; a single word the
  // monumental scale; variant 2's dominant title sits a step above the rest.
  const titleSize = model.longTitle
    ? m.titleLong
    : model.shortTitle
      ? m.titleShort
      : model.variant === 2
        ? m.titleMonumental
        : m.title;
  // Three lines, overflow hidden, never an ellipsis: the max-height is three
  // times the leading, in em so it tracks the font size.
  const titleClamp = model.longTitle
    ? "leading-snug max-h-[4.125em]"
    : model.shortTitle
      ? "leading-none tracking-wide max-h-[3em]"
      : m.titleClamp;
  const motifOpacity = lightGround ? "opacity-30" : "opacity-35";

  // The model's tier flags decide what the full sizes show; today both equal
  // !mini, but the presentation honors the model, not a re-derived guess.
  const eyebrow = model.showEyebrow ? (
    <span className={cx("block uppercase", dims.eyebrow, m.eyebrow)}>
      {t(GENRE_KEYS[model.channel])}
    </span>
  ) : null;
  const rule = (centered: boolean) => (
    <div aria-hidden="true" className={cx("mt-1 h-[1px] w-8 bg-current/40", centered && "mx-auto")} />
  );
  const titleEl = (
    <span className={cx("block overflow-hidden break-words font-normal italic", SERIF, titleSize, titleClamp)}>
      {titleText}
    </span>
  );
  // Fall D's hairline under a one-word title (spec 864): the rule() grammar's
  // current/40, so it reads on light and dark grounds alike; centered with the
  // classic composition, left-aligned on the other two. The miniature renders
  // no title and so no hairline.
  const shortTitleRule = model.shortTitle ? (
    <div
      aria-hidden="true"
      className={cx("w-6 h-[1px] bg-current/40 mt-3", model.variant === 0 && "mx-auto")}
    />
  ) : null;
  // The author dim is per size (R19: wizard/hero 0.75, shelf 0.70, raised per
  // channel where AA needs it); the miniature shows no author at all.
  const authorOpacity = size === "mini" ? undefined : dims.author[size];
  const authorEl = model.showAuthor ? (
    <span className={cx("block", authorOpacity, m.author)}>{authorText}</span>
  ) : null;

  return (
    <div
      data-variant={model.variant}
      data-channel={model.channel}
      style={{ width: model.width, height: model.height }}
      className={cx(
        "relative flex flex-col overflow-hidden rounded-l-none select-none",
        m.rightRadius,
        model.monogram ? "justify-end" : "justify-between",
        palette.ground,
        palette.ink,
        RIM,
        SHADOW,
        m.padding,
        className,
      )}
    >
      {/* 1. The spine crease — above everything, never interactive. */}
      <div
        aria-hidden="true"
        className={cx("pointer-events-none absolute inset-y-0 left-0 z-20", m.creaseWidth, lightGround ? CREASE_PALE : CREASE)}
      />
      {/* 2. The blind-deboss boundary — culled at the miniature. */}
      {!model.monogram && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-[6px] rounded-r-[4px] border border-cover-deboss/20"
        />
      )}

      {model.monogram ? (
        // The miniature: the monogram alone, low and left (Sektion 04).
        <div className={cx("relative z-10 pb-0.5", m.pad)}>
          <span className={cx("block text-[9px] font-bold leading-none", SERIF)}>
            {model.monogramText}
          </span>
        </div>
      ) : model.variant === 0 ? (
        // 0 — centered classic: the focus rests in the optical middle.
        <>
          <div className="relative z-10 text-center">
            {eyebrow}
            {rule(true)}
          </div>
          {model.showVignette && (
            <div className="relative z-10 my-auto flex justify-center py-2">
              <GenreMotif channel={model.channel} className={cx(m.motif, motifOpacity)} />
            </div>
          )}
          <div className={cx("relative z-10 text-center", m.titleSpacing, m.pad)}>
            {titleEl}
            {shortTitleRule}
            {authorEl}
          </div>
        </>
      ) : model.variant === 1 ? (
        // 1 — offset axis: the vignette shifts off the spine, the type stays left.
        <>
          <div className={cx("relative z-10", m.pad)}>
            {eyebrow}
            {rule(false)}
          </div>
          {model.showVignette && (
            <div className="relative z-10 my-auto pl-8">
              <GenreMotif channel={model.channel} className={cx(m.motif, motifOpacity)} />
            </div>
          )}
          <div className={cx("relative z-10", m.titleSpacing, m.pad)}>
            {titleEl}
            {shortTitleRule}
            {authorEl}
          </div>
        </>
      ) : (
        // 2 — monumental whitespace: an edge vignette beside the eyebrow, the
        // title owns the middle, the author under a rule at the foot.
        <>
          <div className={cx("relative z-10 flex items-start justify-between", m.pad)}>
            <div>
              {eyebrow}
              {rule(false)}
            </div>
            {model.showVignette && (
              <GenreMotif channel={model.channel} className={cx(m.motifEdge, "shrink-0 opacity-40")} />
            )}
          </div>
          <div className={cx("relative z-10 my-auto", m.pad)}>
            {titleEl}
            {shortTitleRule}
          </div>
          {model.showAuthor && (
            <div className={cx("relative z-10 border-t border-current/20 pt-2", dims.foot, m.pad, m.author)}>
              {authorText}
            </div>
          )}
        </>
      )}
    </div>
  );
}
