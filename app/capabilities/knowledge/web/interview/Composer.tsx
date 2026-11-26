/**
 * The interview's composer (W9 Task 10): the two chips («Keine Ahnung» and
 * «Alles vorschlagen lassen»), the free-text field and the send button.
 * While a turn runs every control is disabled and the placeholder names the
 * wait; a failed turn leaves the writer's text exactly where it stood, so
 * the field is never cleared by a write that did not land.
 */
import { useTranslation } from "@shell/lib/i18n";
import { FOCUS } from "@shell/ui/card";
import { Icon } from "@shell/ui/icons";

export function Composer({
  text,
  onChange,
  onSend,
  onNoIdea,
  onFillAll,
  disabled,
}: {
  text: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onNoIdea: () => void;
  onFillAll: () => void;
  disabled: boolean;
}) {
  const t = useTranslation();
  const canSend = !disabled && text.trim() !== "";

  return (
    <div data-testid="entity-interview-composer" className="shrink-0 border-t border-rule px-3 py-2">
      <div className="mb-1.5 flex items-center gap-1.5">
        <button
          type="button"
          data-testid="entity-interview-no-idea"
          disabled={disabled}
          onClick={onNoIdea}
          className={`rounded border border-rule bg-surface-container-low px-2 py-0.5 text-[10px] text-muted transition-colors hover:text-foreground disabled:cursor-not-allowed disabled:opacity-60 ${FOCUS}`}
        >
          {t("knowledge.interview.noIdea")}
        </button>
        <button
          type="button"
          data-testid="entity-interview-fill-all"
          disabled={disabled}
          onClick={onFillAll}
          className={`rounded border border-rule bg-surface-container-low px-2 py-0.5 text-[10px] text-muted transition-colors hover:text-foreground disabled:cursor-not-allowed disabled:opacity-60 ${FOCUS}`}
        >
          {t("knowledge.interview.fillAll")}
        </button>
      </div>
      <div className="flex items-end gap-1.5 rounded-[var(--radius-control)] border border-rule bg-card px-2 py-1 shadow-card">
        <textarea
          aria-label={t("knowledge.interview.placeholder")}
          placeholder={disabled ? t("knowledge.interview.waiting") : t("knowledge.interview.placeholder")}
          rows={2}
          disabled={disabled}
          value={text}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key !== "Enter" || event.shiftKey) return;
            event.preventDefault();
            if (canSend) onSend();
          }}
          className="min-h-8 flex-1 resize-none bg-transparent px-1 py-1 text-body text-foreground placeholder:text-muted focus:outline-none disabled:cursor-not-allowed disabled:text-muted"
        />
        <button
          type="button"
          data-testid="entity-interview-send"
          aria-label={t("knowledge.interview.send")}
          title={t("knowledge.interview.send")}
          disabled={!canSend}
          onClick={onSend}
          className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-[var(--radius-control)] bg-primary text-primary-foreground transition-colors hover:opacity-95 disabled:cursor-not-allowed disabled:bg-surface-container disabled:text-muted ${FOCUS}`}
        >
          <Icon name="arrowRight" size={15} />
        </button>
      </div>
      <p className="mt-1 text-[10px] text-muted">{t("knowledge.interview.hint")}</p>
    </div>
  );
}
