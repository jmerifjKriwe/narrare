import { Link } from "@tanstack/react-router";
import { Fragment, useLayoutEffect, useRef, type KeyboardEvent } from "react";

import { client } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import { activeLocale, applyLocale, chosenLocale, type Locale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";
import { Icon } from "@shell/ui/icons";

import { readPreSetupLocale, storePreSetupLocale } from "./preSetupLocale";

/**
 * The wizard's shared header chrome — one home for the bar the four ported
 * steps repeat. The review found three copies diverging, with the narrow-
 * screen wrap fix landed in only one; the brand and context line, the four-
 * step progress stepper, the DE|EN|FR switcher with its pre-setup mirror
 * contract and the honestly disabled help button now live here once, and
 * each step mounts the header with its own number.
 *
 * The inner line wraps (`flex-wrap gap-y-2`): at narrow widths the longer
 * French brand line („Configuration du projet") pushed the right control
 * group past the viewport (scrollWidth 405 at 390px). Wrapping keeps every
 * control reachable on every step, in every catalog; on wide lines nothing
 * changes.
 *
 * The stepper speaks the drafts' three states: the steps before the active
 * one are done (the check, success, a Link back that keeps the wizard's
 * search), the active step wears `aria-current="step"` — step one keeps the
 * first draft's numbered-badge face, steps two and three the primary pulse
 * face, step four the binding draft's calm pill (a ringed chip with the
 * pulsing primary dot) — and the rest wait with their number. The last step
 * never links forward: nothing follows the binding.
 */

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The shell's focus ring on every control the header offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The draft draws DE|EN|FR with DE leading; the switcher keeps that order. */
const SWITCHER_ORDER: readonly Locale[] = ["de", "en", "fr"];

/** The four steps in the drafts' order; the done ones link back, keeping
 *  the search. The const keeps each `to` a literal the router checks. */
const STEPS = [
  { key: "setup.wizard.step1", to: "/setup/basis" },
  { key: "setup.wizard.step2", to: "/setup/structure" },
  { key: "setup.wizard.step3", to: "/setup/ai-rules" },
  { key: "setup.wizard.step4", to: "/setup/provisioning" },
] as const satisfies readonly { key: MessageKey; to: string }[];

export function WizardHeader({ activeStep }: { activeStep: 1 | 2 | 3 | 4 }) {
  const t = useTranslation();
  const locale = activeLocale();
  const switcherRefs = useRef<Partial<Record<Locale, HTMLElement | null>>>({});

  // The pre-setup mirror, the welcome's contract: adopt before paint when
  // the settings row holds no choice yet.
  useLayoutEffect(() => {
    if (chosenLocale() !== null) return;
    const mirrored = readPreSetupLocale();
    if (mirrored !== null) applyLocale(mirrored);
  }, []);

  /** Apply and persist a locale — the welcome switcher's contract: the
   *  structural 409 keeps the mirror, a success clears it, any other refusal
   *  restores the prior choice. */
  async function chooseLocale(next: Locale) {
    if (next === activeLocale()) return;
    const previous = chosenLocale();
    applyLocale(next);
    storePreSetupLocale(next);
    try {
      const { response } = await client.PATCH("/api/settings", { body: { locale: next } });
      if (response.status === 409) return; // setup required: the mirror stands
      if (!response.ok) throw new Error(`refused: ${response.status}`);
      storePreSetupLocale(null);
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
    } catch {
      applyLocale(previous);
      storePreSetupLocale(previous);
    }
  }

  /** The switcher's keyboard contract, the welcome's: arrows cycle and wrap,
   *  Home/End jump to the ends, Space/Enter select; the move selects and
   *  focuses. */
  function radioKey(event: KeyboardEvent<HTMLElement>, at: number) {
    const span = SWITCHER_ORDER.length;
    let next: number;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") next = (at + 1) % span;
    else if (event.key === "ArrowLeft" || event.key === "ArrowUp") next = (at - 1 + span) % span;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = span - 1;
    else if (event.key === " " || event.key === "Enter") next = at;
    else return;
    event.preventDefault();
    const code = SWITCHER_ORDER[next];
    void chooseLocale(code);
    switcherRefs.current[code]?.focus();
  }

  return (
    // Sticky, the drafts' surface-bright bar; the inner line wraps so the
    // right controls stay reachable in every catalog at every width.
    <header className="sticky top-0 z-30 w-full bg-surface shadow-sm">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 gap-y-2 px-6 py-3">
        {/* Brand & context */}
        <div className="flex items-center gap-2.5">
          <div
            className={`${SERIF} flex h-8 w-8 items-center justify-center rounded bg-primary text-emph font-semibold text-primary-foreground shadow-inner`}
          >
            N
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-emph font-semibold tracking-tight text-foreground">
                {t("setup.welcome.wordmark")}
              </span>
              <span aria-hidden="true" className="text-meta text-outline-variant">
                /
              </span>
              <span className="text-label font-medium text-muted">{t("setup.basis.context")}</span>
            </div>
            <p className="text-eyebrow uppercase tracking-wider text-muted">
              {t("setup.welcome.year")} • {t("setup.welcome.edition")}
            </p>
          </div>
        </div>

        {/* Stepper — done steps check back, the active one stands out, the
            rest wait; the states derive from the step that mounts us. */}
        <nav
          aria-label={t("setup.wizard.progress")}
          className="hidden items-center gap-1 rounded-lg border border-border bg-surface-container-low px-3 py-1.5 md:flex"
        >
          {STEPS.map((entry, at) => {
            const n = at + 1;
            return (
              <Fragment key={entry.key}>
                {at > 0 && (
                  <span aria-hidden="true" className="px-1 text-meta text-outline-variant">
                    ›
                  </span>
                )}
                {n < activeStep ? (
                  <Link
                    to={entry.to}
                    search={true}
                    className={`flex items-center gap-2 rounded px-2.5 py-1 text-label font-medium text-success transition-colors hover:bg-surface-container ${FOCUS}`}
                  >
                    <Icon name="check" size={15} />
                    <span>{t(entry.key)}</span>
                  </Link>
                ) : n === activeStep ? (
                  activeStep === 1 ? (
                    // Step one keeps the first draft's numbered-badge face.
                    <div
                      aria-current="step"
                      className="flex items-center gap-2 rounded bg-surface-container-lowest px-2.5 py-1 text-label font-semibold text-primary shadow-sm"
                    >
                      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
                        {n}
                      </span>
                      <span>{t(entry.key)}</span>
                    </div>
                  ) : activeStep === 4 ? (
                    // Step four wears the binding draft's calm pill: the
                    // work is underway, the chip rings it rather than
                    // flooding it — the pulse is the only movement.
                    <div
                      aria-current="step"
                      className="flex items-center gap-1.5 rounded-full border border-outline-variant/70 bg-surface-container-lowest px-3 py-1 text-label font-semibold text-primary shadow-sm"
                    >
                      <span aria-hidden="true" className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary" />
                      <span>{t(entry.key)}</span>
                    </div>
                  ) : (
                    <div
                      aria-current="step"
                      className="flex items-center gap-2 rounded bg-primary px-2.5 py-1 text-label font-semibold text-primary-foreground shadow-sm"
                    >
                      <span aria-hidden="true" className="h-1.5 w-1.5 animate-pulse rounded-full bg-secondary-container" />
                      <span>{t(entry.key)}</span>
                    </div>
                  )
                ) : (
                  <span className="flex items-center gap-1.5 px-2 py-1 text-label text-muted">
                    <span className="flex h-4 w-4 items-center justify-center rounded-full border border-outline-variant text-[10px]">
                      {n}
                    </span>
                    <span>{t(entry.key)}</span>
                  </span>
                )}
              </Fragment>
            );
          })}
        </nav>

        {/* Language switcher & controls */}
        <div className="flex items-center gap-3">
          <div
            role="radiogroup"
            aria-label={t("setup.welcome.language")}
            className="inline-flex rounded-lg border border-border bg-surface-container-lowest p-0.5 text-meta"
          >
            {SWITCHER_ORDER.map((code, at) => (
              <button
                key={code}
                type="button"
                role="radio"
                aria-label={catalogs[code]["locale.name"]}
                aria-checked={code === locale}
                tabIndex={code === locale ? 0 : -1}
                ref={(node) => {
                  switcherRefs.current[code] = node;
                }}
                onKeyDown={(event) => radioKey(event, at)}
                onClick={() => void chooseLocale(code)}
                className={
                  code === locale
                    ? `rounded bg-surface-container-high px-2 py-0.5 font-semibold text-primary ${FOCUS}`
                    : `rounded px-2 py-0.5 text-muted transition-colors hover:text-foreground ${FOCUS}`
                }
              >
                {code.toUpperCase()}
              </button>
            ))}
          </div>
          <div aria-hidden="true" className="h-4 w-px bg-border" />
          {/* The handbook does not exist yet: honestly disabled (gap doc). */}
          <button
            type="button"
            disabled
            title={t("setup.basis.help")}
            aria-label={t("setup.basis.help")}
            className="flex h-8 w-8 cursor-not-allowed items-center justify-center rounded-lg text-muted opacity-50"
          >
            <Icon name="menuBook" size={18} />
          </button>
        </div>
      </div>
    </header>
  );
}
