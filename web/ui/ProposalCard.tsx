import { Button } from "react-aria-components";
import { useId, type ReactNode } from "react";

import { useTranslation, type MessageKey } from "@shell/lib/i18n";

/**
 * The "AI proposes, you decide" primitive of spec §5.6: a titled card with
 * the proposed text and the two decisions — take it or drop it. The caller
 * owns the meaning: the title names what is proposed, `onAccept`/
 * `onDiscard` decide what taking or dropping does. `children` is the
 * consumer's own extras (an edit affordance, provenance) between the body
 * and the actions. React-Aria's Button carries the keyboard contract.
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
    <section
      aria-labelledby={headingId}
      className="mt-4 rounded-lg border border-border bg-card p-4"
    >
      <h3 id={headingId} className="text-sm font-semibold">
        {t(titleKey)}
      </h3>
      <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-muted">{body}</p>
      {children}
      <div className="mt-3 flex gap-2">
        <Button
          onPress={onAccept}
          className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground data-focus-visible:outline-none data-focus-visible:ring-2 data-focus-visible:ring-focus"
        >
          {t("proposal.accept")}
        </Button>
        <Button
          onPress={onDiscard}
          className="rounded-md border border-border px-3 py-2 text-sm font-medium hover:bg-panel data-focus-visible:outline-none data-focus-visible:ring-2 data-focus-visible:ring-focus"
        >
          {t("proposal.discard")}
        </Button>
      </div>
    </section>
  );
}
