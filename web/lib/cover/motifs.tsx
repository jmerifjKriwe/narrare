/**
 * The eight hairline genre vignettes — the cover's only imagery, ported
 * from the archived Stitch spec (docs/design/stitch/screens/library/
 * cover-system.html, Sektion 02). The spec draws on a 40×40 grid centered
 * at (20,20); the cover's viewBox is 48×48, so every coordinate shifts +4:
 * the motifs keep the spec's sizes and sit centered, small and hairline.
 *
 * Pure presentation: no state, no i18n, no palette. stroke="currentColor"
 * lets the cover's ink token drive every line; the two filled dots (the
 * historical beacon, the fallback seal's center) are the spec's own
 * fill="currentColor" marks against the root's fill="none".
 */

import type { ReactElement } from "react";

import type { CoverChannel } from "./cover";

/** One channel's inner geometry; the shared hairline wrapper is below. */
const MOTIFS: Record<CoverChannel, ReactElement> = {
  // Radar- & Planetenbahnen, pulsierender Signalvektor: concentric rings
  // r=14 (dashed) and r=6, the pulse line through both poles.
  scifi: (
    <>
      <circle cx="24" cy="24" r="14" strokeDasharray="2 2" />
      <circle cx="24" cy="24" r="6" />
      <line x1="24" x2="24" y1="6" y2="42" />
    </>
  ),
  // Himmelsstern & Astralbogen: the four-point star inside a dotted orbit.
  fantasy: (
    <>
      <path d="M24 9 L28 20 L39 24 L28 28 L24 39 L20 28 L9 24 L20 20 Z" />
      <circle cx="24" cy="24" r="12" strokeDasharray="1 3" />
    </>
  ),
  // Architektonischer Grundriss, Fluchtlinien: the 20×20 blueprint rect,
  // its two escape lines and the room's center mark.
  mystery: (
    <>
      <rect x="14" y="14" width="20" height="20" />
      <line x1="14" x2="34" y1="24" y2="24" />
      <line x1="24" x2="24" y1="14" y2="34" />
      <circle cx="24" cy="24" r="3" />
    </>
  ),
  // Organischer Wellenfluss & Horizontmarke: two Q-curve wave bands and
  // the small horizon sun above them.
  literary: (
    <>
      <path d="M12 28 Q 24 18, 36 28" />
      <path d="M16 32 Q 24 24, 32 32" />
      <circle cx="24" cy="16" r="3" />
    </>
  ),
  // Maritime Leuchtfeuer-Geometrie & Nebelkante: the lighthouse triangle,
  // the fog edge it stands on, the lit beacon (the spec's filled dot).
  historical: (
    <>
      <polygon points="24,10 30,38 18,38" />
      <line x1="12" x2="36" y1="38" y2="38" />
      <circle cx="24" cy="18" r="2" fill="currentColor" />
    </>
  ),
  // Verschlungene Knospen & botanische Linien: two intertwined buds on
  // the shared stem line.
  romance: (
    <>
      <circle cx="20" cy="24" r="9" />
      <circle cx="28" cy="24" r="9" />
      <path d="M24 15 L24 33" />
    </>
  ),
  // Seismische Risslinie & Pulsausschlag: one crack that spikes into a
  // pulse and settles back to the baseline.
  thriller: <path d="M8 24 L18 24 L22 12 L26 36 L30 24 L40 24" />,
  // Atelier-Siegel: the dashed monogram square with its center dot (the
  // spec's filled mark) — Tabula Rasa for Lyrik and every unknown genre.
  fallback: (
    <>
      <rect x="16" y="16" width="16" height="16" strokeDasharray="2 2" />
      <circle cx="24" cy="24" r="2" fill="currentColor" />
    </>
  ),
};

/**
 * One hairline vignette. The wrapper carries the whole grammar — 48×48
 * viewBox, fill none, currentColor stroke at 1.1, aria-hidden — so the
 * caller only picks the channel and the size (className); the ink comes
 * from the text color the cover sets.
 */
export function GenreMotif({
  channel,
  className,
}: {
  channel: CoverChannel;
  className?: string;
}): ReactElement {
  return (
    <svg
      viewBox="0 0 48 48"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.1}
      aria-hidden="true"
      data-channel={channel}
      className={className}
    >
      {MOTIFS[channel]}
    </svg>
  );
}