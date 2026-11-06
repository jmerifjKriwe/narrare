/**
 * The one search normalization: NFD, strip combining marks, lowercase. What
 * every matcher compares, so "öffnen" answers to "offnen", "fur" to
 * "Fürstenwald", and case never decides a match. It lived as a private
 * helper of the palette's matching (`lib/commands.ts`) until the rail's
 * filter needed the same semantics — one definition, two callers, so the
 * palette and the rail can never disagree about what a match is.
 */
export function normalize(text: string): string {
  return text.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();
}
