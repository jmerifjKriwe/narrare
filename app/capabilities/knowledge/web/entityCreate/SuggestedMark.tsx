/**
 * The interview's provenance mark on a create-dialog part (W9 Task 11): the
 * wire says the model wrote it, so the dialog says «vorgeschlagen» beside it.
 * The same mark the proposal card draws, in the create dialog's own folder.
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
