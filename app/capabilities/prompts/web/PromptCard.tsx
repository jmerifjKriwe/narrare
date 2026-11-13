import type { components } from "@shell/lib/api/schema";
import { useTranslation } from "@shell/lib/i18n";
import { Button } from "@shell/ui/Button";

import { PromptEditor } from "./PromptEditor";
import { keyLabelOf } from "./promptLabels";

type PromptSummary = components["schemas"]["PromptSummary"];

/** The two override tiers, as the API's `scope` field names them. */
type PromptScope = "global" | "novel";

/** A scope chip: the name of the tier the lines under it speak about. */
function Chip({ children }: { children: string }) {
  return <span className="rounded-full bg-panel px-2 py-0.5 text-label">{children}</span>;
}

/**
 * One key's block: the two scope chips with their honest state lines, the
 * explicit actions, and the editor when one of this key's scopes is open.
 * Every fact comes from the summary row — the page mints none of its own.
 * The blocks are rows of one list panel, separated by rules — never cards
 * inside the card (L5).
 */
export function PromptCard(props: {
  summary: PromptSummary;
  novelSelected: boolean;
  focusNonce?: number;
  editor: { scope: PromptScope; novelId: string; novelTitle: string | null } | null;
  onEdit: (scope: PromptScope) => void;
  onClose: () => void;
  onSaved: () => void;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const t = useTranslation();
  const { summary, novelSelected, focusNonce, editor, onEdit, onClose, onSaved, onDirtyChange } = props;
  const label = keyLabelOf(summary.key, t);
  return (
    <li className="border-b border-rule py-3 first:pt-0 last:border-b-0 last:pb-0">
      <h2 className="flex flex-wrap items-baseline gap-2 text-body font-medium">
        {label}
        <code className="text-label font-normal text-muted">{summary.key}</code>
      </h2>
      <p className="mt-1 text-body text-muted">{summary.bundled_summary}</p>

      <div className="mt-3 flex flex-col gap-3">
        <div>
          <Chip>{t("prompts.scope.global")}</Chip>
          <p className="mt-1 text-label text-muted">
            {summary.override_global
              ? t("prompts.globalOverridden")
              : t("prompts.globalBundled")}
          </p>
          <div className="mt-2">
            <Button variant="secondary" onClick={() => onEdit("global")}>
              {summary.override_global ? t("prompts.edit") : t("prompts.createGlobal")}
            </Button>
          </div>
        </div>
        {summary.novel_scopable ? (
          <div>
            <Chip>{t("prompts.scope.novel")}</Chip>
            {novelSelected ? (
              <>
                <p className="mt-1 text-label text-muted">
                  {summary.override_novel
                    ? t("prompts.novelOverridden")
                    : t("prompts.inherits", {
                        state: summary.override_global
                          ? t("prompts.inheritsFrom.global")
                          : t("prompts.inheritsFrom.bundled"),
                      })}
                </p>
                <div className="mt-2">
                  <Button variant="secondary" onClick={() => onEdit("novel")}>
                    {summary.override_novel ? t("prompts.editNovel") : t("prompts.create")}
                  </Button>
                </div>
              </>
            ) : (
              <p className="mt-1 text-label text-muted">{t("prompts.pickNovel")}</p>
            )}
          </div>
        ) : null}
      </div>

      {editor === null ? null : (
        <PromptEditor
          promptKey={summary.key}
          keyLabel={label}
          scope={editor.scope}
          novelId={editor.novelId}
          novelTitle={editor.novelTitle}
          focusNonce={focusNonce}
          onClose={onClose}
          onSaved={onSaved}
          onDirtyChange={onDirtyChange}
        />
      )}
    </li>
  );
}
