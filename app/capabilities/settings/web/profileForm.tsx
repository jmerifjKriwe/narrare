/**
 * The Autoren-Profil section (W7 Task 3) — the settings-allgemein draft's
 * one dirty form, on the shell's tokens. Two fields: the author name (the
 * user block's label; the email answers as the fallback when none is
 * stored, so the hint names the real address) and the daily goal (the
 * atelier's discipline; empty is the honest unset).
 *
 * The contract is the novel-update rule: ONE dirty form, and the save
 * carries only the fields the writer changed — an absent field keeps, a
 * carried null clears (the name back to the email label, the goal back to
 * no goal). The locale rides along always carried (the schema's own rule),
 * handed through from the row untouched. A value reverted to the stored
 * one is no change; a pristine save makes no ask at all. Refusals keep
 * every answer: a 422 names itself as the atelier's refusal, anything else
 * wears the family's loss-free line, and the retry re-runs the very ask.
 *
 * The two addresses the user-block menu doors land on live here: the
 * section is `#profil-sektion`, the goal field `#tagesziel-feld` — a hash
 * navigation focuses the field it names (the page's own effect).
 *
 * Draft deviations, deliberate: the goal input is text with a numeric
 * keyboard (the house parse contract — grouped de figures like „1.000"
 * round-trip; the drafted `type=number` would refuse them), and the
 * footer's drafted „Browser-Speicher" line reads „lokales Atelier" — the
 * row lives on the instance, not in a browser store; the card stays honest.
 */
import { useState } from "react";

import { formatNumber } from "@shell/lib/format";
import { useTranslation } from "@shell/lib/i18n";
import { useUpdateSettings } from "@shell/lib/query";
import { Icon } from "@shell/ui/icons";

/** The shell's focus ring on every control the form offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The row's answers, as the strict read carried them. */
export type ProfileRow = {
  locale: string | null;
  author_name: string | null;
  daily_goal_words: number | null;
  email: string | null;
};

/** A daily-goal answer: a whole number within the column's bounds, the
 *  honest unset (null — the empty input), or the refusal. The kernel's own
 *  bounds (WORD_GOAL_MIN 1 … the Integer column's ceiling), mirrored —
 *  a capability never imports another (rule 1), so the writing family's
 *  parser is copied here, not imported. */
export type DailyGoalAnswer = number | null | "invalid";

export function parseDailyGoal(raw: string): DailyGoalAnswer {
  const trimmed = raw.trim();
  if (trimmed === "") return null;
  const digits = trimmed.replace(/[.,\u00a0\u202f ]/g, "");
  if (!/^\d+$/.test(digits)) return "invalid";
  const value = Number(digits);
  if (!Number.isSafeInteger(value) || value < 1 || value > 2_147_483_647) return "invalid";
  return value;
}

/** A stored goal as the input opens on it: the locale's grouped figure,
 *  the unset as the empty field. */
function formatGoalInput(value: number | null): string {
  return value === null ? "" : formatNumber(value);
}

export function ProfileForm({ row }: { row: ProfileRow }) {
  const t = useTranslation();
  const updateSettings = useUpdateSettings();

  // The answers, transient against the stored baseline. The badge shows on
  // any keystroke away from it; the save diffs by VALUE, so a field typed
  // and reverted is no write.
  const storedName = row.author_name ?? "";
  const storedGoalRaw = formatGoalInput(row.daily_goal_words);
  const [name, setName] = useState(storedName);
  const [goalRaw, setGoalRaw] = useState(storedGoalRaw);
  const [goalError, setGoalError] = useState(false);
  const [error, setError] = useState<(Error & { status?: number }) | null>(null);

  const dirty = name !== storedName || goalRaw !== storedGoalRaw;
  const busy = updateSettings.isPending;

  /** The one save: validate, diff against the row, ride the mutation with
   *  only the dirtied fields. The locale always rides (the schema's rule). */
  function save() {
    const goal = parseDailyGoal(goalRaw);
    if (goal === "invalid") {
      setGoalError(true);
      return;
    }
    setGoalError(false);
    const trimmed = name.trim();
    const changes: { authorName?: string | null; dailyGoalWords?: number | null } = {};
    if (trimmed !== storedName) changes.authorName = trimmed === "" ? null : trimmed;
    if (goal !== row.daily_goal_words) changes.dailyGoalWords = goal;
    // Nothing carried is no write — the pristine save rests honestly.
    if (Object.keys(changes).length === 0) return;
    setError(null);
    updateSettings.mutate(
      { locale: row.locale, ...changes },
      {
        // The saved truth stands in the fields at once; the invalidated
        // row answers with exactly the same values.
        onSuccess: () => {
          setName(trimmed);
          setGoalRaw(formatGoalInput(goal));
        },
        onError: (cause) => setError(cause),
      },
    );
  }

  /** Verwerfen: back to the row's answers, every face retired. */
  function discard() {
    setName(storedName);
    setGoalRaw(storedGoalRaw);
    setGoalError(false);
    setError(null);
  }

  const inputClass = `w-full rounded border bg-panel px-3.5 py-2.5 text-body text-foreground transition-colors focus:border-primary ${FOCUS}`;

  return (
    <section id="profil-sektion" aria-labelledby="settings-profile-heading" className="space-y-6 pt-2">
      <div className="flex items-baseline justify-between border-b border-border pb-2.5">
        <div>
          <h2 id="settings-profile-heading" className={`${SERIF} text-title font-normal text-foreground`}>
            {t("settings.profile.heading")}
          </h2>
          <p className="mt-0.5 text-meta text-muted">{t("settings.profile.sub")}</p>
        </div>
        {dirty && (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-2.5 py-0.5 text-[11px] font-medium text-primary">
            <span aria-hidden="true" className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary" />
            {t("settings.profile.dirty")}
          </span>
        )}
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          save();
        }}
        className="space-y-6 rounded-lg border border-border bg-card p-6 shadow-sm"
      >
        {/* Feld: Autorenname — the email answers as the label when the
            field is left empty; the hint names the real address. */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label htmlFor="settings-author-name" className="block text-eyebrow font-semibold uppercase tracking-wider text-foreground">
              {t("settings.author.label")}
            </label>
            <span className="text-[11px] text-muted">{t("settings.author.meta")}</span>
          </div>
          <input
            id="settings-author-name"
            name="author_name"
            type="text"
            value={name}
            placeholder={t("settings.author.placeholder")}
            maxLength={200}
            onChange={(event) => setName(event.target.value)}
            className={inputClass}
          />
          <p className="text-[11px] leading-relaxed text-muted">
            {row.email !== null
              ? t("settings.author.hint.email", { email: row.email })
              : t("settings.author.hint.neutral")}
          </p>
        </div>

        {/* Feld: Tagesziel — empty is the honest unset, the carried null
            the save carries. This div is the menu's second address. */}
        <div id="tagesziel-feld" className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label htmlFor="settings-daily-goal" className="block text-eyebrow font-semibold uppercase tracking-wider text-foreground">
              {t("settings.goal.label")}
            </label>
            <span className="text-[11px] text-muted">{t("settings.goal.meta")}</span>
          </div>
          <div className="relative w-48">
            <input
              id="settings-daily-goal"
              name="daily_goal_words"
              type="text"
              inputMode="numeric"
              value={goalRaw}
              aria-invalid={goalError}
              onChange={(event) => {
                setGoalRaw(event.target.value);
                setGoalError(false);
              }}
              className={`${inputClass} pr-14 tabular-nums`}
            />
            <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-meta text-muted">
              {t("settings.goal.unit")}
            </span>
          </div>
          {goalError ? (
            <p role="alert" className="text-[11px] leading-relaxed text-danger">
              {t("settings.goal.invalid")}
            </p>
          ) : (
            <p className="text-[11px] leading-relaxed text-muted">{t("settings.goal.hint")}</p>
          )}
        </div>

        {/* The refusal faces: answers stay, the retry re-runs the ask. */}
        {error !== null && (
          <div role="alert" className="flex flex-wrap items-center justify-between gap-2 rounded border border-danger/40 bg-panel px-3 py-2">
            <p className="text-meta text-danger">
              {error.status === 422 ? t("settings.refused") : t("settings.error")}
            </p>
            <button
              type="button"
              disabled={busy}
              onClick={save}
              className={`rounded border border-border bg-surface-container-low px-3 py-1.5 text-meta font-medium text-foreground transition-colors hover:bg-surface-container ${FOCUS} ${busy ? "cursor-not-allowed opacity-50" : ""}`}
            >
              {t("settings.retry")}
            </button>
          </div>
        )}

        {/* The footer: the honest local note, then Verwerfen / Speichern. */}
        <div className="flex flex-col justify-between gap-4 border-t border-rule pt-4 sm:flex-row sm:items-center">
          <div className="flex items-center gap-2 text-meta text-muted">
            <span className="shrink-0 text-primary">
              <Icon name="clock" size={16} />
            </span>
            <span>{t("settings.profile.saveNote")}</span>
          </div>
          <div className="flex items-center gap-3 self-end sm:self-auto">
            <button
              type="button"
              disabled={busy}
              onClick={discard}
              className={`rounded px-4 py-2 text-meta font-medium text-muted transition-colors hover:bg-surface-container hover:text-foreground ${FOCUS} ${busy ? "cursor-not-allowed opacity-50" : ""}`}
            >
              {t("settings.discard")}
            </button>
            <button
              type="submit"
              disabled={busy}
              className={`rounded bg-primary px-4 py-2 text-meta font-semibold text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS} ${busy ? "cursor-not-allowed opacity-60" : ""}`}
            >
              {busy ? t("settings.saving") : t("settings.save")}
            </button>
          </div>
        </div>
      </form>

      {/* The offline note: the draft's Offline-Kompensation card, the
          backend's local truth in its info tone. */}
      <div className="mt-4 flex items-start gap-3 rounded-lg border border-border bg-panel p-4 text-meta">
        <span className="mt-0.5 shrink-0 text-primary">
          <Icon name="info" size={16} />
        </span>
        <div>
          <h3 className="font-medium text-foreground">{t("settings.offline.title")}</h3>
          <p className="mt-0.5 leading-relaxed text-muted">{t("settings.offline.body")}</p>
        </div>
      </div>
    </section>
  );
}
