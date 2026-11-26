/**
 * The interview's provenance mark on a proposal or a create-dialog part (W9
 * Task 11): the wire says the model wrote it, so the face says
 * «vorgeschlagen» beside it. One component for the proposal card and the
 * prefilled dialog; it lives on the capability's own shared shelf because
 * only knowledge draws it.
 */
import { useTranslation } from "@shell/lib/i18n";

export function SuggestedMark() {
  const t = useTranslation();
  return (
    <span className="rounded bg-secondary-container/50 px-1 py-0.5 font-mono text-[9px] text-primary">
      {t("knowledge.interview.suggested")}
    </span>
  );
}
