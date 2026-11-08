import { useState } from "react";

import { client } from "@shell/lib/api/client";
import type { components } from "@shell/lib/api/schema";
import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import { Field, Select } from "@shell/ui/field";
import { Notice } from "@shell/ui/Notice";

import { KIND_LABELS, LABEL_ROW } from "./ProvidersSection";

type Model = components["schemas"]["ModelRead"];
type Assignment = components["schemas"]["AssignmentRead"];
type TaskEffective = components["schemas"]["TaskEffectiveRead"];

/**
 * The task labels the catalog carries, keyed by task. The list of tasks comes
 * from the server (`KNOWN_TASK_KEYS`); this map only supplies words. The
 * server's `assignable` decides whether a row gets a select, so a new key is
 * routable without a frontend edit and only needs its label (a missing label
 * falls back to the generic one, never to the raw key).
 */
const TASK_LABELS: Record<string, MessageKey> = {
  "writing.continuation": "settings.task.writing.continuation",
  "chat.ask": "settings.task.chat.ask",
  "knowledge.extract-entities": "settings.task.knowledge.extract-entities",
  "knowledge.check-consistency": "settings.task.knowledge.check-consistency",
  "settings.test": "settings.tasks.settings.test",
};

/**
 * A model as the task rows and their select options name it: the provider it
 * hangs off, then the model string — `"{provider} · {model}"`. The row's own
 * name is the model list's word; here the facts are the ones that decide a
 * task.
 */
export function labelOf(model: Model): string {
  return `${model.provider_name} · ${model.model}`;
}

/**
 * The tasks section: one row per known task key, the select pointing it at a
 * model, the line beneath naming what actually answers — the cascade can
 * serve a sibling's assignment or the default, not the stored choice. The
 * options and the effective lines compose their labels from the models list,
 * so both speak `"{provider} · {model}"` and no second naming can drift.
 */
export function TasksSection({
  models,
  assignments,
  tasks,
  reload,
}: {
  models: Model[] | null;
  assignments: Assignment[];
  tasks: TaskEffective[];
  reload: () => Promise<void>;
}) {
  const t = useTranslation();
  const [failure, setFailure] = useState(false);

  async function assign(taskKey: string, modelId: string): Promise<void> {
    try {
      const { response } = await client.PUT("/api/settings/assignments/{task_key}", {
        params: { path: { task_key: taskKey } },
        body: { profile_id: modelId === "" ? null : modelId },
      });
      if (!response.ok) {
        setFailure(true);
        return;
      }
      setFailure(false);
      await reload();
    } catch {
      // A rejected fetch has no response to inspect: the page still says so,
      // in the same place a server-reachable failure appears.
      setFailure(true);
    }
  }

  return (
    <section aria-labelledby="settings-assignments-heading" className="mt-5">
      <h2 id="settings-assignments-heading" className="text-emph font-semibold">
        {t("settings.assignments")}
      </h2>

      {failure ? (
        <Notice tone="danger" live="alert" className="mt-3">
          {t("settings.profiles.errorAction")}
        </Notice>
      ) : null}

      <div className="mt-3 flex flex-col gap-2">
        {tasks.map((task) => {
          const assigned = assignments.find((row) => row.task_key === task.task_key);
          const labelKey = TASK_LABELS[task.task_key];
          const label = labelKey === undefined ? t("settings.tasks.unknown") : t(labelKey);
          const kindKey = KIND_LABELS[task.kind];
          if (!task.assignable) {
            // An audit-only key (the settings probe's) has no serving tier and
            // no assignment to offer: one labelled line explains what it is.
            // A plain text pair, not a `Field`: there is no control for a
            // label to point at.
            return (
              <div key={task.task_key} className={`${LABEL_ROW} text-label font-medium`}>
                <span>{label}</span>
                <p className="font-normal text-muted">{t("settings.profiles.taskAuditOnly")}</p>
              </div>
            );
          }
          // What actually answers, not the stored choice: the cascade can
          // serve a sibling's assignment or the default from here.
          const serving = (models ?? []).find((model) => model.id === task.profile_id);
          const effective =
            serving !== undefined
              ? t("settings.assignments.via", { model: labelOf(serving) })
              : t("settings.assignments.environment", {
                  kind: kindKey === undefined ? task.kind : t(kindKey),
                });
          return (
            <Field key={task.task_key} label={label} className={LABEL_ROW}>
              <Select
                value={assigned?.profile_id ?? ""}
                onChange={(event) => void assign(task.task_key, event.target.value)}
                aria-describedby={`settings-task-effective-${task.task_key}`}
                className="max-w-64"
              >
                <option value="">{t("settings.assignments.auto")}</option>
                {(models ?? []).map((model) => (
                  <option key={model.id} value={model.id}>
                    {labelOf(model)}
                  </option>
                ))}
              </Select>
              <p
                id={`settings-task-effective-${task.task_key}`}
                className="col-start-2 min-w-0 break-words text-label font-normal text-muted"
              >
                {effective}
              </p>
            </Field>
          );
        })}
      </div>
    </section>
  );
}
