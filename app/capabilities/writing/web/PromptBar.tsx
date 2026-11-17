/**
 * The floating prompt bar (W4 Task 16) — the scene-centric draft's bar
 * (light face wins) on the shell's tokens: the Stil trigger, the inline
 * input, the „Weiterschreiben" primary and the three quick pills, floating
 * over the editor stage's foot.
 *
 * Everything the bar asks is REAL (D5): the primary with an empty input is
 * the bare continuation, a carried instruction rides the endpoint's prompt
 * parameter, and each pill sends its own localized label as that parameter.
 * The bound mirrors the schema client-side (1–2000 raw characters, no trim
 * — the chat question's precedent, Task 15's pin): an over-long instruction
 * is refused by name before the wire, the app's field-error family
 * (aria-invalid + the described danger line).
 *
 * Honest faces: the Stil trigger keeps its geometry and claims nothing —
 * INTERIM #878, no style presets exist to pick (gap row 13). While the
 * stream runs, KACHEL 7's busy face stands: the spinner, the generating
 * label and Stoppen (a chosen stop dismisses, never an error face). The
 * draft's „(Stil: Lakonisch)" is mock style data and never ships; the
 * error face lives at the scene tail (KACHEL 8), the bar rests idle again.
 * The pills' drafted copy is genericized — „Dialog mit ARIA vertiefen" and
 * „Sensor-Details ausschmücken" name the draft novel's own facts; the
 * brief's three ship, localized en/de/fr.
 */
import { useId, useState } from "react";

import { useTranslation } from "@shell/lib/i18n";
import { Icon } from "@shell/ui/icons";

import { PROMPT_MAX_LENGTH, promptWithinBound, type Continuation } from "./workspace";

/** The shell's focus ring on every control the bar offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The drafted three — the emoji is the draft's own mark, the label is the
 *  prompt that rides the parameter (localized, du-tone). */
const PILLS = [
  { emoji: "⚡", key: "writing.workspace.promptBar.pillTension" },
  { emoji: "💬", key: "writing.workspace.promptBar.pillDialogue" },
  { emoji: "🔍", key: "writing.workspace.promptBar.pillDetail" },
] as const;

export function PromptBar({ continuation }: { continuation: Continuation }) {
  const t = useTranslation();
  const [value, setValue] = useState("");
  const errorId = useId();
  // The live mirror: the refusal stands while the instruction is over-long
  // and clears the moment it is back within the bound — the field-error
  // family's own discipline (the shelf dialog's title line).
  const overBound = value !== "" && !promptWithinBound(value);

  function send(prompt?: string) {
    continuation.start(prompt);
  }

  function submit() {
    // The empty input is the bare continuation — no prompt, no refusal.
    if (value === "") {
      send(undefined);
      return;
    }
    if (overBound) return; // the refusal already stands; nothing reaches the wire
    send(value);
  }

  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-5 z-30 flex justify-center px-4">
      <div className="pointer-events-auto w-full max-w-[42rem] space-y-2 rounded-2xl border border-border bg-panel/95 p-2.5 shadow-overlay backdrop-blur-md">
        {continuation.phase === "streaming" ? (
          /* KACHEL 7 — the busy face: the spinner, the honest generating
             label (no style claim), the abort that dismisses. */
          <div
            role="status"
            className="flex items-center justify-between gap-2 rounded-lg border border-border bg-surface-container-low p-2"
          >
            <span className="flex min-w-0 items-center gap-2">
              <span
                aria-hidden="true"
                className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border border-area-writing border-t-transparent"
              />
              <span className="truncate text-meta text-muted">
                {t("writing.workspace.promptBar.busy")}
              </span>
            </span>
            <button
              type="button"
              onClick={continuation.dismiss}
              className={`flex shrink-0 items-center gap-1 rounded border border-danger/40 bg-panel px-2.5 py-1 text-meta font-medium text-danger transition-colors hover:bg-danger/5 ${FOCUS}`}
            >
              <Icon name="stopCircle" size={13} />
              <span>{t("writing.workspace.promptBar.stop")}</span>
            </button>
          </div>
        ) : (
          <form
            aria-label={t("writing.workspace.promptBar.label")}
            className="space-y-2"
            onSubmit={(event) => {
              event.preventDefault();
              submit();
            }}
          >
            <div className="flex items-center gap-2">
              {/* The Stil trigger — INTERIM #878: the geometry stays, the
                  neutral „—" claims nothing, the note names the wait. */}
              <button
                type="button"
                disabled
                title={t("writing.workspace.promptBar.styleNote")}
                className="flex shrink-0 cursor-not-allowed items-center gap-1 rounded-lg border border-border bg-surface-container-low px-2.5 py-1.5 text-meta text-muted"
              >
                <span>{t("writing.workspace.promptBar.style")}</span>
                <span className="font-mono text-foreground">—</span>
                <Icon name="unfoldMore" size={12} />
              </button>
              <input
                type="text"
                value={value}
                onChange={(event) => setValue(event.target.value)}
                aria-label={t("writing.workspace.promptBar.inputLabel")}
                aria-invalid={overBound}
                aria-describedby={overBound ? errorId : undefined}
                placeholder={t("writing.workspace.promptBar.placeholder")}
                className="min-w-0 flex-1 bg-transparent px-2 text-body text-foreground outline-none placeholder:text-muted"
              />
              <button
                type="submit"
                className={`flex shrink-0 items-center gap-1.5 rounded-lg bg-primary px-3.5 py-1.5 text-meta font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS}`}
              >
                <Icon name="spark" size={14} />
                <span>{t("writing.workspace.promptBar.continue")}</span>
              </button>
            </div>
            {overBound && (
              <p id={errorId} role="alert" className="px-1 text-meta leading-tight text-danger">
                {t("writing.workspace.promptBar.boundError", { max: PROMPT_MAX_LENGTH })}
              </p>
            )}
            <div className="flex items-center gap-1.5 overflow-x-auto pt-0.5">
              {PILLS.map((pill) => (
                <button
                  key={pill.key}
                  type="button"
                  onClick={() => send(t(pill.key))}
                  className={`flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full border border-border bg-surface-container-low px-2.5 py-1 text-[11px] text-muted transition-colors hover:bg-surface-container hover:text-foreground ${FOCUS}`}
                >
                  <span aria-hidden="true">{pill.emoji}</span>
                  <span>{t(pill.key)}</span>
                </button>
              ))}
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
