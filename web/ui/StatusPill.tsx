import { useTranslation, type MessageKey } from "../lib/i18n";

/**
 * The shelf's four status states (spec §5.9): the hero's "in progress" and
 * the cards' draft, planning and review, as `shelf.html` and its dark leg
 * draw them. The bar's save chip keeps the shell's `shell.sync*` vocabulary
 * instead (deviation #2); this is the shelf's own status set.
 */
export type StatusKind = "active" | "draft" | "planning" | "review";

/** The state's word, from the writing catalog so a pill speaks the
 *  reader's language. The card states reuse the drafted shelf's own labels. */
const LABEL: Record<StatusKind, MessageKey> = {
  active: "shelf.hero.active",
  draft: "shelf.statusDraft",
  planning: "shelf.statusPlanning",
  review: "shelf.statusReview",
};

/**
 * The state's paint: the token utilities over the shell's status triples
 * (`--pill-<kind>-ground/-ink/-rule`, globals.css). The light half draws no
 * rule — the token is `transparent` there — while the dark screen's literal
 * hairline binds, so the border utility rides both halves rather than
 * switching on and off with the theme.
 */
const PAINT: Record<StatusKind, string> = {
  active: "bg-pill-active-ground text-pill-active-ink border-pill-active-rule",
  draft: "bg-pill-draft-ground text-pill-draft-ink border-pill-draft-rule",
  planning:
    "bg-pill-planning-ground text-pill-planning-ink border-pill-planning-rule",
  review: "bg-pill-review-ground text-pill-review-ink border-pill-review-rule",
};

/**
 * A status pill: the drafted eyebrow-tracked micro-label on its own ground.
 * One primitive for the hero and the cards, so a status cannot wear two
 * different paints on the same shelf. The interim status *value* is the
 * caller's (every book is a draft until #784); the hues are real.
 */
export function StatusPill({ kind }: { kind: StatusKind }) {
  const t = useTranslation();
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-eyebrow uppercase ${PAINT[kind]}`}
    >
      {t(LABEL[kind])}
    </span>
  );
}
