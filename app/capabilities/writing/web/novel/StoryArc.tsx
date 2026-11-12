import { useTranslation } from "@shell/lib/i18n";

/**
 * The rail's drafted tension arc (screens/writing/workspace.html, the
 * "Spannungsbogen" widget): the area-writing gradient curve with the
 * current chapter's marker riding it at `position/total` — where the
 * writer stands in the book — and the caption naming the chapter the dot
 * stands for. What the draft shows that no field backs stays out and is
 * named for the follow-up where it hides (spec §6).
 */

/**
 * The drafted curve, segment for segment: the draft's `M/Q/T/T` path with
 * the smooth-quadratic Ts resolved to their own control points (each T's
 * control is the previous control reflected through the previous end), so
 * the marker can find the point beneath its x without reading the DOM —
 * jsdom lays out nothing, and the unit test pins the dot to the hand-solved
 * points of the same numbers.
 */
const ARC_SEGMENTS = [
  { p0: [0, 40], cp: [40, 32], p1: [70, 22] },
  { p0: [70, 22], cp: [100, 12], p1: [140, 10] },
  { p0: [140, 10], cp: [180, 8], p1: [200, 34] },
] as const;

/** The viewBox the draft draws on: 200 wide, 48 tall. */
const ARC_WIDTH = 200;

/** One coordinate pair of a quadratic Bézier at parameter t. */
function pointAt(a: number, c: number, b: number, t: number): number {
  const u = 1 - t;
  return u * u * a + 2 * u * t * c + t * t * b;
}

/**
 * The point on the curve whose x is `x`: the segment whose span holds it,
 * then the root of that segment's quadratic in t. Each segment's x is
 * monotone (its control sits between its endpoints), so the in-range root
 * is the point, not a guess.
 */
function arcPoint(x: number): { x: number; y: number } {
  for (const { p0, cp, p1 } of ARC_SEGMENTS) {
    if (x < p0[0] || x > p1[0]) continue;
    // x(t) − x = 0 as at² + bt + c:  a = x0 − 2cx + x1, b = 2(cx − x0).
    const qa = p0[0] - 2 * cp[0] + p1[0];
    const qb = 2 * (cp[0] - p0[0]);
    const qc = p0[0] - x;
    let t: number;
    if (Math.abs(qa) < 1e-9) {
      t = -qc / qb;
    } else {
      const root = Math.sqrt(qb * qb - 4 * qa * qc);
      const near = (-qb + (qa < 0 ? root : -root)) / (2 * qa);
      const far = (-qb - (qa < 0 ? root : -root)) / (2 * qa);
      t = near >= 0 && near <= 1 ? near : far;
    }
    return { x, y: pointAt(p0[1], cp[1], p1[1], t) };
  }
  // Off both spans: the curve's nearer end.
  const end = ARC_SEGMENTS[ARC_SEGMENTS.length - 1]!;
  return x < 0 ? { x: 0, y: end.p0[1] } : { x: ARC_WIDTH, y: end.p1[1] };
}

/**
 * The foot widget's card, as the draft draws it: the eyebrow row, then the
 * curve. The marker is `position` of `total` — one-based, the chapter's own
 * number — and only while a chapter stands: no open chapter, no dot, no
 * caption, the labeled curve alone.
 */
export function StoryArc({ position, total }: { position: number; total: number }) {
  const t = useTranslation();
  const placed = total > 0 && position >= 1;
  const fraction = placed ? Math.min(position / total, 1) : 0;
  const marker = arcPoint(fraction * ARC_WIDTH);
  // The caption centres under the dot; near the ends it steps inside the
  // card instead of hanging over its edge. The dot itself never moves.
  const captionLeft = Math.min(Math.max((marker.x / ARC_WIDTH) * 100, 10), 90);
  return (
    <div className="mt-3 shrink-0 px-3">
      <div className="rounded-[var(--radius-control)] bg-surface-container-low p-3 shadow-sm">
        <div className="mb-2 flex items-center justify-between gap-2">
          <span className="text-eyebrow uppercase text-muted">{t("workspace.railArcLabel")}</span>
          <span
            // interim: no plot data — follow-up filed in W3's index
            // (the draft's meta reads "Akt I - Höhepunkt"; the app holds
            // no acts or beats, so the slot says so in words instead of
            // inventing a phase).
            className="shrink-0 font-medium text-meta text-area-writing"
          >
            {t("workspace.railArcNone")}
          </span>
        </div>
        {/* The draft's own viewBox and curve; `overflow-visible` is the
            draft's, so the dot at the path's ends may kiss the padding. The
            gradient is the draft's one hue at its three depths — the token's
            value, never a hex — and the pulse stills under reduced motion. */}
        <svg
          aria-hidden="true"
          className="h-12 w-full overflow-visible text-area-writing"
          viewBox="0 0 200 48"
        >
          <defs>
            <linearGradient id="railArcGradient" x1="0%" x2="100%" y1="0%" y2="0%">
              <stop offset="0%" stopColor="var(--area-writing)" stopOpacity={0.3} />
              <stop offset="50%" stopColor="var(--area-writing)" stopOpacity={0.8} />
              <stop offset="100%" stopColor="var(--area-writing)" stopOpacity={0.2} />
            </linearGradient>
          </defs>
          <path
            d="M 0,40 Q 40,32 70,22 T 140,10 T 200,34"
            fill="none"
            stroke="url(#railArcGradient)"
            strokeLinecap="round"
            strokeWidth={2.5}
          />
          {placed ? (
            <circle
              className="animate-pulse motion-reduce:animate-none"
              cx={marker.x}
              cy={marker.y}
              fill="var(--area-writing)"
              r={4.5}
            />
          ) : null}
        </svg>
        {/* The draft writes the caption inside the svg at 9px, which the
            rail's narrower column scales under legibility; it is real text
            (the chapter's number), so it renders as HTML at the meta step
            and keeps its AA ink. */}
        {placed ? (
          <div className="relative h-0">
            <span
              className="absolute -translate-x-1/2 whitespace-nowrap text-meta text-secondary"
              style={{ left: `${captionLeft}%` }}
            >
              {t("workspace.railArcChapter", { n: position })}
            </span>
          </div>
        ) : null}
      </div>
    </div>
  );
}
