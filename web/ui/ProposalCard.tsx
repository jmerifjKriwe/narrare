import { Button } from "react-aria-components";
import { useId, type ReactNode } from "react";

import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import { buttonClass } from "@shell/ui/Button";

/**
 * The "AI proposes, you decide" primitive of spec §5.6: a titled card with
 * the proposed text and the two decisions — take it or drop it. The caller
 * owns the meaning: the title names what is proposed, `onAccept`/
 * `onDiscard` decide what taking or dropping does. `children` is the
 * consumer's own extras (an edit affordance, provenance) between the body
 * and the actions. React-Aria's Button carries the keyboard contract; its
 * paint is the button matrix (`buttonClass`), so the card's decisions wear
 * exactly what every button in the app wears. The pair is two equals —
 * neither decision fills a primary, which stays the surface's own action
 * (L1) — and both stay always visible: the decision is the card's point,
 * not a step behind an expansion.
 */
export function ProposalCard({
  titleKey,
  body,
  onAccept,
  onDiscard,
  children,
}: {
  titleKey: MessageKey;
  body: string;
  onAccept: () => void;
  onDiscard: () => void;
  children?: ReactNode;
}) {
  const t = useTranslation();
  const headingId = useId();
  return (
    // The labelled section is the card's name for assistive tech and for
    // tests: a named <section> is a region, addressable by its heading.
    // The title is a card title (§8.2): text-emph, 600.
    <section
      aria-labelledby={headingId}
      className="mt-4 rounded-[var(--radius-lg)] border border-border bg-card p-3"
    >
      <h3 id={headingId} className="text-emph font-semibold">
        {t(titleKey)}
      </h3>
      <p className="mt-2 whitespace-pre-wrap text-body leading-relaxed text-muted">{body}</p>
      {children}
      <div className="mt-3 flex gap-2">
        <Button onPress={onAccept} className={buttonClass("secondary", "md")}>
          {t("proposal.accept")}
        </Button>
        <Button onPress={onDiscard} className={buttonClass("secondary", "md")}>
          {t("proposal.discard")}
        </Button>
      </div>
    </section>
  );
}
