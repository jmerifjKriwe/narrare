/**
 * The Aufgaben section (W8 Task 9) — the approved draft's third section on
 * the shell's tokens: one row per known task key, the model select and the
 * output-profile select, the resolved number beside them.
 *
 * The row's two truths are kept apart on purpose:
 * - The selects edit the STORED assignment (the `["settings-assignments"]`
 *   read), shown as the editor's own state; the no-assignment option is the
 *   cascade's honest face, not a fake claim — clearing falls down the
 *   resolution cascade, and the chip says what actually answers.
 * - The chip answers the EFFECTIVE read (the `["settings-tasks"]` read):
 *   `resolved_output_tokens` is the number the next call reserves, shown as
 *   is — uncapped when no ceiling is stored, `min`-ed with the model's
 *   stored ceiling when one is (the asterisk's own condition, computed from
 *   the effective pair — the read's own stored profile, the assignments
 *   read's custom number where the read can only say `custom` — never from
 *   the editor's selection, so a pick in flight or refused can neither
 *   invent a cap nor hide one). The fake driver's mark rides the
 *   chip when the cascade's answer is the local fake — never the draft's
 *   „0 Tok. (Offline)“ invention.
 *
 * The PUT is whole: a save carries the model AND the profile choice, because
 * the assignment's profile column has no two-state semantics — an omitted
 * profile states `balanced` by that fact. That shape is why a model switch
 * under a custom choice the field cannot carry HOLDS — no number, or one
 * above the target model's known limit: it sends nothing rather than
 * carrying `balanced` or the refused number in behind the writer's back,
 * and rides the save the completed number (or a named profile) lands.
 * `settings.test` is audit-only and never a dropdown: its row states the
 * fact, no selects, no chip.
 *
 * The rows reconcile against the reads that land behind them (a model
 * delete cascades its assignments at the database): a row whose model
 * vanished re-seeds from the assignments read's current answer, while a
 * save in flight or a refusal on display keeps the writer's answers.
 */
import { useState } from "react";

import type { Assignment, Model, TaskEffective } from "@shell/lib/api/client";
import { formatNumber } from "@shell/lib/format";
import { useTranslation } from "@shell/lib/i18n";
import type { MessageKey } from "@shell/lib/i18n";
import { Icon } from "@shell/ui/icons";

import { useAssignTask, type WireError } from "../aiRulesQuery";
import { parseDailyGoal } from "../profileForm";
import { FamilyFace } from "./providersSection";

const COMPACT_SELECT =
  "h-8 w-full rounded bg-background px-2.5 text-label text-foreground outline-none transition-shadow focus:border-focus focus:ring-1 focus:ring-focus";

/** The named output profiles in the kernel's own order, with the targets
 *  the kernel constants hold (W8 ruling 5) — the catalog copy carries the
 *  same numbers beside them. */
const PROFILE_OPTIONS: ReadonlyArray<{ name: string; target: number; labelKey: MessageKey }> = [
  { name: "quick", target: 1_024, labelKey: "settings.ai.profile.quick" },
  { name: "balanced", target: 4_096, labelKey: "settings.ai.profile.balanced" },
  { name: "long_texts", target: 12_288, labelKey: "settings.ai.profile.long" },
  { name: "comprehensive", target: 32_768, labelKey: "settings.ai.profile.comprehensive" },
];

/** The draft's four rows, mapped onto the real task keys; `settings.test`
 *  joins them as the audit row that is never a dropdown. */
const TASK_META: Record<
  string,
  { titleKey: MessageKey; bodyKey: MessageKey; icon: "editNote" | "chat" | "hub" | "balance" }
> = {
  "writing.continuation": { titleKey: "settings.ai.task.continuation.title", bodyKey: "settings.ai.task.continuation.body", icon: "editNote" },
  "chat.ask": { titleKey: "settings.ai.task.chat.title", bodyKey: "settings.ai.task.chat.body", icon: "chat" },
  "knowledge.extract-entities": { titleKey: "settings.ai.task.extract.title", bodyKey: "settings.ai.task.extract.body", icon: "hub" },
  "knowledge.check-consistency": { titleKey: "settings.ai.task.consistency.title", bodyKey: "settings.ai.task.consistency.body", icon: "balance" },
  "settings.test": { titleKey: "settings.ai.task.audit.title", bodyKey: "settings.ai.task.audit.body", icon: "balance" },
};

/** One row's editor state: the stored assignment as the selects open on it,
 *  a refusal held beside the answers it refused to eat. */
type RowState = {
  profileId: string | null;
  /** A vocabulary name, the sentinel `"custom"`, or `null` before any
   *  choice rode this row (the profile column's balanced default shows as
   *  the named default — the truthful face the tasks read answers). */
  profile: string | null;
  customRaw: string;
  error: WireError | null;
};

export function TasksSection({
  tasks,
  assignments,
  models,
}: {
  tasks: TaskEffective[];
  assignments: Assignment[];
  models: Model[];
}) {
  const t = useTranslation();
  const assignTask = useAssignTask();

  // The rows' editor states, initialised from the stored assignments; a
  // task without one opens on the cascade option and the named default.
  const [rows, setRows] = useState<Record<string, RowState>>(() => {
    const stored = new Map(assignments.map((entry) => [entry.task_key, entry]));
    const initial: Record<string, RowState> = {};
    for (const task of tasks) {
      if (!task.assignable) continue;
      const row = stored.get(task.task_key);
      initial[task.task_key] = {
        profileId: row?.profile_id ?? null,
        profile: row?.output_profile ?? "balanced",
        customRaw: row?.output_profile_custom === null || row?.output_profile_custom === undefined ? "" : String(row.output_profile_custom),
        error: null,
      };
    }
    return initial;
  });

  function setRow(taskKey: string, patch: Partial<RowState>) {
    setRows((current) => ({ ...current, [taskKey]: { ...current[taskKey], ...patch } }));
  }

  // The rows reconcile against the reads that land behind them: an
  // assignment the database cascaded away (its model was deleted) cannot
  // keep standing in the editor — the select would wear an id that is
  // neither an option nor a stored truth, and the row's next save would
  // submit it to a 404. The trigger is both reads' answer: the
  // assignments read carries no row for the task any more, and the
  // editor's id names a model the models read no longer carries — the
  // reset is the cascade's honest answer (the cascade option, the named
  // default, resting). A row whose own save stands in flight or whose
  // refusal is on display keeps the writer's answers: reconciliation
  // waits, and the writer's next action re-runs the ask.
  const modelIds = new Set(models.map((model) => model.id));
  for (const task of tasks) {
    const state = rows[task.task_key];
    if (!task.assignable || state === undefined) continue;
    if (state.profileId === null || modelIds.has(state.profileId)) continue;
    if (assignments.some((entry) => entry.task_key === task.task_key)) continue;
    if (state.error !== null) continue;
    if (assignTask.isPending && assignTask.variables?.taskKey === task.task_key) continue;
    setRow(task.task_key, { profileId: null, profile: "balanced", customRaw: "", error: null });
  }

  /** The carried profile choice as the wire's shape: a vocabulary name, or
   *  the custom number itself (never the `"custom"` word — the schema
   *  refuses it). The named default carries by name, so a save never
   *  silently re-states a choice the row never made. */
  function carriedProfile(state: RowState): string | number {
    if (state.profile === "custom") {
      const parsed = parseDailyGoal(state.customRaw);
      return typeof parsed === "number" ? parsed : "balanced";
    }
    return state.profile ?? "balanced";
  }

  function saveRow(taskKey: string, next: RowState) {
    assignTask.mutate(
      { taskKey, profileId: next.profileId, outputProfile: carriedProfile(next) },
      {
        // The landed ask's own echo is the row's next state: a cleared
        // assignment stores nothing and the backend answers the default —
        // the select re-syncs to that (the cascade option, balanced,
        // resting), so the editor never shows a choice nothing stores. A
        // refusal keeps every answer: the selects stay as the writer set
        // them, the family face names the why, nothing is reverted behind
        // their back. The next save re-runs the very ask.
        onSuccess: (assignment) =>
          setRow(taskKey, {
            profileId: assignment.profile_id,
            profile: assignment.output_profile,
            customRaw:
              assignment.output_profile_custom === null || assignment.output_profile_custom === undefined
                ? ""
                : String(assignment.output_profile_custom),
            error: null,
          }),
        onError: (cause) => setRow(taskKey, { error: cause }),
      },
    );
  }

  return (
    <section id="sektion-aufgaben" aria-labelledby="ai-rules-tasks-heading" className="space-y-4">
      <div className="space-y-0.5">
        <h2 id="ai-rules-tasks-heading" className="text-title font-semibold text-foreground">
          {t("settings.ai.section.tasks")}
        </h2>
        <p className="max-w-3xl text-meta leading-relaxed text-muted">{t("settings.ai.tasks.sub")}</p>
      </div>

      <div className="space-y-3">
        {tasks.map((task) => {
          const meta = TASK_META[task.task_key] ?? {
            titleKey: "settings.ai.task.audit.title",
            bodyKey: "settings.ai.task.audit.body",
            icon: "balance" as const,
          };
          const state = rows[task.task_key];

          if (!task.assignable || state === undefined) {
            /* The audit row: no selects, no chip — the fact, stated. */
            return (
              <article
                key={task.task_key}
                data-testid="task-row"
                data-task-key={task.task_key}
                className="flex flex-col gap-4 rounded-lg border border-border bg-card p-4 lg:flex-row lg:items-center lg:justify-between"
              >
                <div className="flex items-start gap-3.5 lg:max-w-md">
                  <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded bg-primary/10 text-primary">
                    <Icon name={meta.icon} size={18} />
                  </span>
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <h3 className="text-emph font-semibold text-foreground">{t(meta.titleKey)}</h3>
                      <span className="rounded bg-surface px-1.5 py-0.5 text-eyebrow uppercase tracking-wider text-muted">
                        {t("settings.ai.task.audit.badge")}
                      </span>
                    </div>
                    <p className="text-body leading-relaxed text-muted">{t(meta.bodyKey)}</p>
                  </div>
                </div>
                <p className="shrink-0 text-meta text-muted">{t("settings.ai.task.auditNote")}</p>
              </article>
            );
          }

          const fake = task.kind === "fake";
          // The cap note derives from the EFFECTIVE pair, never the editor's
          // selection: the tasks read names the stored choice beside the
          // number a call reserves, so a named profile compares against its
          // own constant, and where the read can only say „custom“ the
          // stored number is the assignments read's `output_profile_custom`
          // — the two reads are one invalidation family, so they never
          // disagree about what is stored. A pick in flight or refused names
          // nothing the chip can compare against: a refusal cannot dress a
          // mismatched selection up as a ceiling's cap, and a true cap
          // survives a mismatched selection untold.
          const storedAssignment = assignments.find((entry) => entry.task_key === task.task_key);
          const target =
            task.output_profile === "custom"
              ? (storedAssignment?.output_profile_custom ?? null)
              : (PROFILE_OPTIONS.find((entry) => entry.name === task.output_profile)?.target ?? null);
          const capped =
            typeof target === "number" &&
            task.resolved_output_tokens !== null &&
            task.resolved_output_tokens < target;
          // The field's own faces: a typed answer that parses to no whole
          // number within the column's bounds is invalid here, before any
          // wire ask — and a parsed number above the assigned model's
          // KNOWN output limit (the models read's catalog answer, not the
          // stored ceiling) is refused here too, before the call dies on
          // it at the provider. The kernel refuses and never clamps; the
          // editor matches that ethic: the refusal names the limit,
          // nothing is altered behind the writer's back.
          const knownMax =
            models.find((model) => model.id === state.profileId)?.catalog_max_output_tokens ?? null;
          const parsedCustom = state.profile === "custom" ? parseDailyGoal(state.customRaw) : null;
          const customInvalid =
            state.profile === "custom" &&
            state.customRaw.trim() !== "" &&
            parsedCustom === "invalid";
          const customOverLimit = typeof parsedCustom === "number" && knownMax !== null && parsedCustom > knownMax;

          return (
            <article
              key={task.task_key}
              data-testid="task-row"
              data-task-key={task.task_key}
              className="space-y-3 rounded-lg border border-border bg-card p-4"
            >
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex items-start gap-3.5 lg:max-w-md">
                <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded bg-primary/10 text-primary">
                  <Icon name={meta.icon} size={18} />
                </span>
                <div className="space-y-0.5">
                  <h3 className="text-emph font-semibold text-foreground">{t(meta.titleKey)}</h3>
                  <p className="text-body leading-relaxed text-muted">{t(meta.bodyKey)}</p>
                </div>
              </div>

              <div className="flex shrink-0 flex-col gap-3 sm:flex-row sm:items-center">
                <div className="flex min-w-[210px] flex-col gap-1">
                  <span id={`ai-rules-task-model-${task.task_key}`} className="text-eyebrow uppercase tracking-wider text-muted">
                    {t("settings.ai.task.model")}
                  </span>
                  <div className="relative">
                    <select
                      aria-labelledby={`ai-rules-task-model-${task.task_key}`}
                      value={state.profileId ?? ""}
                      onChange={(event) => {
                        const next = { ...state, profileId: event.target.value === "" ? null : event.target.value, error: null };
                        setRow(task.task_key, next);
                        // The hold: an assignment save cannot carry a
                        // custom choice the field does not validate —
                        // the wire has no „custom without its number"
                        // (an omitted profile states `balanced`, a
                        // choice the writer did not make), and a parsed
                        // number above a known limit is the very value
                        // the field's own face refuses, so switching
                        // models while the number does not parse — or
                        // parses over the limit — sends nothing: the
                        // stored row keeps its last valid answer, and
                        // the held switch rides the save that lands
                        // when the number completes within the limit
                        // (blur/Enter) or a named profile is chosen.
                        // The limit asked is the TARGET's: the save
                        // names that model, and the face measures the
                        // number against it one render later — a source
                        // limit would let through what the same face
                        // then flags. Clearing to the cascade is
                        // decisive whatever the field holds — a cleared
                        // assignment stores nothing, the profile rides
                        // meaningless.
                        const targetMax =
                          models.find((model) => model.id === next.profileId)?.catalog_max_output_tokens ??
                          null;
                        const parsed = parseDailyGoal(state.customRaw);
                        const held =
                          next.profileId !== null &&
                          state.profile === "custom" &&
                          (typeof parsed !== "number" || (targetMax !== null && parsed > targetMax));
                        if (!held) saveRow(task.task_key, next);
                      }}
                      className={`${COMPACT_SELECT} appearance-none pr-8`}
                    >
                      <option value="">{t("settings.ai.task.model.cascade")}</option>
                      {models.map((model) => (
                        <option key={model.id} value={model.id}>
                          {model.name}
                        </option>
                      ))}
                    </select>
                    <span className="pointer-events-none absolute right-2.5 top-2 text-muted">
                      <Icon name="selectChevron" size={13} />
                    </span>
                  </div>
                </div>

                <div className="flex min-w-[220px] flex-col gap-1">
                  <span id={`ai-rules-task-profile-${task.task_key}`} className="text-eyebrow uppercase tracking-wider text-muted">
                    {t("settings.ai.task.profile")}
                  </span>
                  <div className="relative">
                    <select
                      aria-labelledby={`ai-rules-task-profile-${task.task_key}`}
                      aria-describedby={
                        state.profileId === null ? `ai-rules-task-profile-note-${task.task_key}` : undefined
                      }
                      // The profile rides the assignment row: without a model
                      // the backend stores nothing (a null PUT clears), so
                      // the select rests with its note — a choice that would
                      // silently revert is never offered.
                      disabled={state.profileId === null}
                      value={state.profile ?? "balanced"}
                      onChange={(event) => {
                        const nextName = event.target.value === "custom" ? "custom" : event.target.value;
                        const next = { ...state, profile: nextName, error: null };
                        setRow(task.task_key, next);
                        // A named profile saves at once; the custom choice
                        // waits for its number (an invalid one rides the
                        // field's own face, never the wire).
                        if (nextName !== "custom") saveRow(task.task_key, next);
                      }}
                      className={`${COMPACT_SELECT} appearance-none pr-8 disabled:cursor-not-allowed disabled:opacity-50`}
                    >
                      {PROFILE_OPTIONS.map((entry) => (
                        <option key={entry.name} value={entry.name}>
                          {t(entry.labelKey)}
                        </option>
                      ))}
                      <option value="custom">{t("settings.ai.profile.custom")}</option>
                    </select>
                    <span className="pointer-events-none absolute right-2.5 top-2 text-muted">
                      <Icon name="selectChevron" size={13} />
                    </span>
                  </div>
                  {state.profileId === null ? (
                    <span
                      id={`ai-rules-task-profile-note-${task.task_key}`}
                      className="block text-[11px] leading-relaxed text-muted"
                    >
                      {t("settings.ai.task.profileNeedsModel")}
                    </span>
                  ) : state.profileId !== null && state.profile === "custom" ? (
                    <div className="space-y-1">
                      <input
                        type="text"
                        inputMode="numeric"
                        aria-label={t("settings.ai.profile.customInput")}
                        value={state.customRaw}
                        aria-invalid={customInvalid || customOverLimit}
                        placeholder={t("settings.ai.profile.customPlaceholder")}
                        onChange={(event) => setRow(task.task_key, { customRaw: event.target.value })}
                        onBlur={() => {
                          const parsed = parseDailyGoal(state.customRaw);
                          if (typeof parsed === "number" && (knownMax === null || parsed <= knownMax))
                            saveRow(task.task_key, { ...state, error: null });
                        }}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            event.preventDefault();
                            const parsed = parseDailyGoal(state.customRaw);
                            if (typeof parsed === "number" && (knownMax === null || parsed <= knownMax))
                              saveRow(task.task_key, { ...state, error: null });
                          }
                        }}
                        className="h-8 rounded bg-background px-2.5 font-mono text-label text-foreground outline-none transition-shadow focus:border-focus focus:ring-1 focus:ring-focus"
                      />
                      {customOverLimit && knownMax !== null && (
                        <span className="block text-[11px] leading-relaxed text-danger">
                          {t("settings.ai.profile.customOverLimit", { tokens: formatNumber(knownMax) })}
                        </span>
                      )}
                      {knownMax !== null && (
                        <span className="block text-[11px] leading-relaxed text-muted">
                          {t("settings.ai.profile.knownMax", { tokens: formatNumber(knownMax) })}
                        </span>
                      )}
                      <span className="block text-[11px] leading-relaxed text-muted">
                        {t("settings.ai.profile.customHint")}
                      </span>
                    </div>
                  ) : null}
                </div>

                <div className="flex min-w-[130px] flex-col items-end justify-end pt-1 sm:pt-4">
                  <div className="flex flex-col items-center">
                    <span
                      title={
                        fake
                          ? t("settings.ai.task.servingFake")
                          : task.profile_name !== null
                            ? t("settings.ai.task.serving", { name: task.profile_name })
                            : undefined
                      }
                      className={`flex items-center gap-1.5 rounded px-2.5 py-1 text-center font-mono text-meta font-medium ${
                        capped ? "bg-warning/15 text-warning" : "bg-surface text-foreground"
                      }`}
                    >
                      {fake && (
                        <span
                          aria-hidden="true"
                          className="h-1.5 w-1.5 shrink-0 rounded-full bg-success"
                          title={t("settings.ai.task.fakeMark")}
                        />
                      )}
                      {task.resolved_output_tokens !== null
                        ? t("settings.ai.task.effective", {
                            tokens: formatNumber(task.resolved_output_tokens),
                          })
                        : "—"}
                    </span>
                    {capped && (
                      <span className="mt-0.5 text-[9px] uppercase tracking-wider text-muted">
                        {t("settings.ai.task.capped")}
                      </span>
                    )}
                    {fake && (
                      <span className="mt-0.5 text-[9px] uppercase tracking-wider text-success">
                        {t("settings.ai.task.fakeMark")}
                      </span>
                    )}
                  </div>
                </div>
                </div>
              </div>

              {state.error !== null && <FamilyFace error={state.error} />}
            </article>
          );
        })}
      </div>
    </section>
  );
}
