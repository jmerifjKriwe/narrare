import { useTranslation, type MessageKey } from "@shell/lib/i18n";

/**
 * The key labels the catalog carries, keyed by prompt key. The list of keys
 * comes from the server (the kernel registry); this map only supplies words.
 * A key the frontend has never heard of still renders, labelled by
 * `prompts.key.unknown`, which is the point of the endpoint: the registry is
 * the only list. The labels are the task names the settings page already
 * carries — one set of words for one registry key.
 */
export const KEY_LABELS: Record<string, MessageKey> = {
  "writing.continuation": "settings.task.writing.continuation",
  "chat.ask": "settings.task.chat.ask",
  "knowledge.extract-entities": "settings.task.knowledge.extract-entities",
  "knowledge.check-consistency": "settings.task.knowledge.check-consistency",
};

/**
 * The refusal vocabulary's labels: the render's own reasons beside the save
 * gate's scope rules. A reason outside the map still renders — as the raw
 * word the server named — so a new refusal is never a blank.
 */
export const REASON_LABELS: Record<string, MessageKey> = {
  syntax: "prompts.reason.syntax",
  "undefined-variable": "prompts.reason.undefined-variable",
  "include-depth": "prompts.reason.include-depth",
  "include-cycle": "prompts.reason.include-cycle",
  "include-missing": "prompts.reason.include-missing",
  forbidden: "prompts.reason.forbidden",
  runtime: "prompts.reason.runtime",
  budget: "prompts.reason.budget",
  "novel-scope": "prompts.reason.novel-scope",
  "unknown-novel": "prompts.reason.unknown-novel",
  contract: "prompts.reason.contract",
};

/** The `t` the hooks hand out, named so helpers can take it as a parameter. */
export type Translate = ReturnType<typeof useTranslation>;

export function keyLabelOf(key: string, t: Translate): string {
  const label = KEY_LABELS[key];
  return label === undefined ? t("prompts.key.unknown") : t(label);
}

export function reasonLabelOf(reason: string, t: Translate): string {
  const label = REASON_LABELS[reason];
  return label === undefined ? reason : t(label);
}
