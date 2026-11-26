/**
 * The Updates section (Task 3): the interval between the app's update checks,
 * in the settings page's own geometry. One field beside the profile form —
 * deliberately not a second dirty form: the save stands only while the answer
 * is valid (one to 365 days) and differs from the stored one, the saved line
 * answers on success, and a refusal keeps the answer beside its retry.
 *
 * The write is the settings page's own PATCH through `useUpdateSettings` (the
 * locale always carried, the schema's rule), read from the strict read's cache
 * at click time — the language contract's own seam, so a choice that landed
 * moments earlier is never reverted by a rendered answer (#933).
 */
import { useState } from "react";

import { useTranslation } from "@shell/lib/i18n";
import { queryClient, useUpdateSettings } from "@shell/lib/query";

/** The shell's focus ring on every control the section offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The interval's bounds, mirrored from the settings schema's own (`ge=1`,
 *  `le=365`): a capability never imports another, and this section is the one
 *  place the web states them. */
const UPDATE_INTERVAL_MIN = 1;
const UPDATE_INTERVAL_MAX = 365;

/** The product default the row carries when the column is unset. */
const UPDATE_INTERVAL_DEFAULT = 7;

/** The row's answers this section reads. */
type UpdatesRow = {
  locale: string | null;
  update_check_interval_days: number | null;
};

/** A typed interval: a whole number inside the bounds, or the refusal. */
function parseUpdateInterval(raw: string): number | "invalid" {
  const trimmed = raw.trim();
  if (!/^\d+$/.test(trimmed)) return "invalid";
  const value = Number(trimmed);
  if (
    !Number.isSafeInteger(value) ||
    value < UPDATE_INTERVAL_MIN ||
    value > UPDATE_INTERVAL_MAX
  ) {
    return "invalid";
  }
  return value;
}

export function UpdatesSection({ row }: { row: UpdatesRow }) {
  const t = useTranslation();
  const updateSettings = useUpdateSettings();

  // The stored answer: the column's own value, the product default when the
  // row carries none. The typed answer is local state beside it.
  const stored = row.update_check_interval_days ?? UPDATE_INTERVAL_DEFAULT;
  const [raw, setRaw] = useState(String(stored));
  const [saved, setSaved] = useState(false);
  // The answer the server accepted: until the row's refetch catches up (or a
  // newer value is accepted), it is no change — an identical second PATCH
  // cannot fire in the window where the rendered row is still pre-write.
  const [lastSaved, setLastSaved] = useState<number | null>(null);
  const [error, setError] = useState<Error | null>(null);

  const interval = parseUpdateInterval(raw);
  const valid = interval !== "invalid";
  const dirty = valid && interval !== stored && interval !== lastSaved;
  const busy = updateSettings.isPending;

  /** The one save: the settings PATCH, the locale carried from the strict
   *  read's cache at click time (the language contract's seam). */
  function save() {
    if (interval === "invalid" || interval === stored || interval === lastSaved) return;
    setSaved(false);
    setError(null);
    const fresh = queryClient.getQueryData<{ locale: string | null }>(["settings", "read"]);
    updateSettings.mutate(
      { locale: fresh === undefined ? row.locale : fresh.locale, update_check_interval_days: interval },
      {
        onSuccess: () => {
          setRaw(String(interval));
          setLastSaved(interval);
          setSaved(true);
        },
        onError: (cause) => setError(cause),
      },
    );
  }

  const inputClass = `w-full rounded border bg-panel px-3.5 py-2.5 text-body text-foreground transition-colors focus:border-primary ${FOCUS}`;

  return (
    <section aria-labelledby="settings-updates-heading" className="space-y-6 pt-2">
      <div className="border-b border-border pb-2.5">
        <h2 id="settings-updates-heading" className={`${SERIF} text-title font-normal text-foreground`}>
          {t("settings.update.heading")}
        </h2>
        <p className="mt-0.5 text-meta text-muted">{t("settings.update.sub")}</p>
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          save();
        }}
        className="space-y-6 rounded-lg border border-border bg-card p-6 shadow-sm"
      >
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label
              htmlFor="settings-update-interval"
              className="block text-eyebrow font-semibold uppercase tracking-wider text-foreground"
            >
              {t("settings.update.label")}
            </label>
            <span className="text-[11px] text-muted">{t("settings.update.meta")}</span>
          </div>
          <div className="relative w-48">
            <input
              id="settings-update-interval"
              name="update_check_interval_days"
              type="number"
              inputMode="numeric"
              min={UPDATE_INTERVAL_MIN}
              max={UPDATE_INTERVAL_MAX}
              step={1}
              value={raw}
              aria-invalid={!valid}
              aria-describedby="settings-update-hint"
              onChange={(event) => {
                setRaw(event.target.value);
                setSaved(false);
                setError(null);
              }}
              className={`${inputClass} pr-14 tabular-nums`}
            />
            <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-meta text-muted">
              {t("settings.update.unit")}
            </span>
          </div>
          {valid ? (
            <p id="settings-update-hint" className="text-[11px] leading-relaxed text-muted">
              {t("settings.update.hint")}
            </p>
          ) : (
            <p id="settings-update-hint" role="alert" className="text-[11px] leading-relaxed text-danger">
              {t("settings.update.invalid")}
            </p>
          )}
        </div>

        {/* The saved line: the write landed, the row holds this answer. */}
        {saved && (
          <p role="status" className="text-meta text-primary">
            {t("settings.update.saved")}
          </p>
        )}

        {/* The refusal face: the answer stays, the retry re-runs the ask. */}
        {error !== null && (
          <div
            role="alert"
            className="flex flex-wrap items-center justify-between gap-2 rounded border border-danger/40 bg-panel px-3 py-2"
          >
            <p className="text-meta text-danger">{t("settings.update.error")}</p>
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

        <div className="flex justify-end border-t border-rule pt-4">
          <button
            type="submit"
            disabled={!dirty || busy}
            className={`rounded bg-primary px-4 py-2 text-meta font-semibold text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS} ${!dirty || busy ? "cursor-not-allowed opacity-60" : ""}`}
          >
            {busy ? t("settings.update.saving") : t("settings.update.save")}
          </button>
        </div>
      </form>
    </section>
  );
}
