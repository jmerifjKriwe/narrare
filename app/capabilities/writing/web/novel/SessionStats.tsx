import { useTranslation } from "@shell/lib/i18n";

/**
 * The rail's drafted session card (screens/writing/workspace.html,
 * "Schreibsitzung heute"): the label and the §6.6 neutral where the words
 * today stand. The card ships, honestly empty — a card that guessed a
 * session would print a number the app does not have (spec §6's interim
 * rule), so nothing here derives, and nothing here counts.
 */
export function SessionStats() {
  const t = useTranslation();
  return (
    <div className="mt-2 shrink-0 px-3 pb-3">
      {/* The draft's own ground: the lowest surface step, a card of its
          own under the arc. */}
      <div className="flex items-center justify-between gap-2 rounded-[var(--radius-control)] bg-surface-container-lowest p-3 shadow-sm">
        <span className="text-meta text-muted">{t("workspace.railSessionLabel")}</span>
        <span
          // interim: no session tracking — follow-up filed in W3's index
          // (the drafted "+412 Wörter", the goal bar and the "82 % erreicht"
          // line all need a session and a goal the app does not hold; the
          // bar and the goal line stay out, the neutral wears the value's
          // place until a real one exists).
          className="font-semibold text-meta text-primary"
        >
          {t("workspace.railSessionNone")}
        </span>
      </div>
    </div>
  );
}
