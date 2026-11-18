/**
 * The inline goal setters (W4 Task 19, D20) — the daily ring's and the
 * chapter-target pill's drafted affordances („Tagesziel anpassen",
 * „Kapitelziel anpassen") answer with one small dialog on the tree
 * dialogs' established weight: one numeric field, the empty input the
 * honest unset (a carried null, never a zero), the dirty-state rule,
 * focus on the field and back to the opener, the shared modal discipline
 * (@shell/ui/modalKeys, #895).
 *
 * The draft draws the affordance, not the setter panel — the geometry is
 * the TreeEditDialog's own (the established pattern the tree menus ride).
 * The daily goal is the atelier's (the settings PATCH, the locale always
 * carried); the chapter goal is the row's own (the chapter PUT, the goal
 * alone — the title stays the rename dialog's). A value unchanged from
 * the stored one closes without a wire ask, the pristine save's rule.
 */

import { useEffect, useId, useRef, useState } from "react";

import { useTranslation } from "@shell/lib/i18n";
import { useSettingsQuery } from "@shell/lib/query";
import { useModalKeys } from "@shell/ui/modalKeys";

import { formatGoalInput, parseWordGoal } from "./bookSettings";
import { ErrorLine, Spinner } from "./TreeDialogs";
import { useUpdateChapter, useUpdateSettings } from "./workspace";

/** The shell's focus ring on every control the dialog offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

export function GoalSetterDialog({
  kind,
  initial,
  novelId,
  chapterId,
  chapterName,
  openerId,
  onClose,
}: {
  /** Which goal the element asked for — the ring's daily or the pill's
   *  chapter. */
  kind: "daily" | "chapter";
  /** The stored goal — null is the honest unset the field opens empty on. */
  initial: number | null;
  /** The chapter goal's row (the daily goal needs neither). */
  novelId?: string;
  chapterId?: string;
  /** The chapter's name, spoken under the heading when it stands. */
  chapterName?: string;
  openerId: string;
  onClose: () => void;
}) {
  const t = useTranslation();
  const settings = useSettingsQuery();
  const updateSettings = useUpdateSettings();
  const updateChapter = useUpdateChapter(novelId ?? "");
  const busy = updateSettings.isPending || updateChapter.isPending;
  // The daily write carries the stored locale (the schema requires it) —
  // until the settings row answers, the save honestly waits.
  const ready = kind === "chapter" || settings.isSuccess;

  const baseline = formatGoalInput(initial);
  const [raw, setRaw] = useState(baseline);
  const [fieldError, setFieldError] = useState(false);
  const [error, setError] = useState(false);
  const dirty = raw !== baseline;

  const panelRef = useRef<HTMLDivElement | null>(null);
  const fieldRef = useRef<HTMLInputElement | null>(null);
  const headingId = useId();
  const fieldId = useId();
  const hintId = useId();

  // Focus lands on the one field; every close returns it to the opener —
  // the element whose affordance raised the setter.
  useEffect(() => {
    fieldRef.current?.focus();
    fieldRef.current?.select();
    return () => {
      document.getElementById(openerId)?.focus();
    };
  }, [openerId]);

  useModalKeys(panelRef, () => {
    if (!busy && !dirty) onClose();
  });

  function save() {
    if (!ready) return;
    setError(false);
    const value = parseWordGoal(raw);
    if (value === "invalid") {
      setFieldError(true);
      return;
    }
    setFieldError(false);
    // The stored answer unchanged is no write — close honestly.
    if (value === initial) {
      onClose();
      return;
    }
    const settle = { onSuccess: onClose, onError: () => setError(true) };
    if (kind === "daily") {
      updateSettings.mutate(
        { locale: settings.data?.locale ?? null, dailyGoalWords: value },
        settle,
      );
    } else if (chapterId !== undefined) {
      updateChapter.mutate({ chapterId, targetWords: value }, settle);
    }
  }

  const label = t(kind === "daily" ? "writing.workspace.goal.dailyLabel" : "writing.workspace.goal.chapterLabel");
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-scrim p-4 backdrop-blur-[1px]"
      onMouseDown={(event) => {
        // The dirty rule: a press outside is not an answer while a typed
        // change stands — the tree edit's own calm.
        if (event.target === event.currentTarget && !busy && !dirty) onClose();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={headingId}
        className="w-full max-w-sm space-y-3 rounded-lg border border-border bg-panel p-5 shadow-overlay"
      >
        <div>
          <h2 id={headingId} className={`${SERIF} text-body font-semibold text-foreground`}>
            {t(kind === "daily" ? "writing.workspace.goal.dailyTitle" : "writing.workspace.goal.chapterTitle")}
          </h2>
          {kind === "chapter" && chapterName !== undefined && (
            <p className="mt-0.5 truncate text-meta text-muted" title={chapterName}>
              {chapterName}
            </p>
          )}
        </div>
        <div>
          <label htmlFor={fieldId} className="mb-1 block text-meta font-medium text-foreground">
            {label}
          </label>
          <input
            id={fieldId}
            ref={fieldRef}
            type="text"
            inputMode="numeric"
            value={raw}
            aria-invalid={fieldError}
            aria-describedby={fieldError ? undefined : hintId}
            onChange={(event) => {
              setRaw(event.target.value);
              setFieldError(false);
            }}
            className={`w-full rounded border bg-surface-container-low px-2.5 py-1.5 font-mono text-body tabular-nums text-foreground ${FOCUS} ${
              fieldError ? "border-danger" : "border-border"
            }`}
          />
          {fieldError ? (
            <p role="alert" className="mt-1 text-meta leading-tight text-danger">
              {t("writing.workspace.goal.invalid")}
            </p>
          ) : (
            <p id={hintId} className="mt-1 text-meta text-muted">
              {t("writing.workspace.goal.hint")}
            </p>
          )}
        </div>
        {error && <ErrorLine message={t("writing.workspace.goal.error")} onRetry={save} />}
        <div className="flex items-center justify-end gap-2 border-t border-rule pt-3">
          <button
            type="button"
            disabled={busy}
            onClick={onClose}
            className={`rounded border border-border px-2.5 py-1.5 text-meta text-muted transition-colors hover:bg-surface-container-low ${FOCUS} ${busy ? "cursor-not-allowed opacity-50" : ""}`}
          >
            {t("writing.workspace.crud.cancel")}
          </button>
          <button
            type="button"
            disabled={busy || !ready}
            onClick={save}
            className={`inline-flex items-center gap-1.5 rounded bg-primary px-3 py-1.5 text-meta font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS} ${busy || !ready ? "cursor-not-allowed opacity-60" : ""}`}
          >
            {busy && <Spinner />}
            {busy ? t("writing.workspace.crud.busy") : t("writing.workspace.crud.save")}
          </button>
        </div>
      </div>
    </div>
  );
}
