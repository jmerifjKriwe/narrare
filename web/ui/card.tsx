/**
 * The card family's shared vocabulary (W5 Task 2's lift — the trio's
 * third consumer, per Task 1's carried review instruction): the eyebrow
 * micro-label above a card's content, the neutral field row, and the
 * focus ring every control a face offers. One home, token-styled; the
 * dock faces import it instead of carrying copies.
 *
 * NeutralRow is the honest gap's geometry — the label left, the dash
 * right, no invented value. The placeholder cards that carried it retire
 * with #866/#867; the dossiers' invented fields (W5 Tasks 3/5) are its
 * next consumers.
 */

/** The draft's card eyebrow — the micro-label above each card's content. */
export const CARD_EYEBROW = "text-[10px] font-bold uppercase tracking-wider text-muted";

/** The shell's focus ring on every control a face offers. */
export const FOCUS = "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** One neutral field row — the label left, the dash right, mono. */
export function NeutralRow({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-between text-meta">
      <span className="text-muted">{label}</span>
      <span className="font-mono text-muted">—</span>
    </div>
  );
}
