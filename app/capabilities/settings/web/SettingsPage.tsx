/**
 * The Allgemein surface (W7 Task 3) — the settings capability's first web
 * page, ported from the owner-approved harmonized `settings-allgemein-2`
 * draft onto the shell's tokens. Three blocks in the draft's geometry:
 *
 * - Sprache & Aussehen, the immediate section: the three language cards and
 *   the theme's three appearance cards apply AT ONCE, through the existing
 *   seams — `useLanguageChoice` (the one language contract; „Dem Browser
 *   folgen" is its null choice) and the shared `useTheme` write (the rail
 *   toggle's own door). No second mechanism exists; a refusal restores.
 *   The theme previews keep their drafted colours on the one palette: the
 *   swatch spans pin `color-scheme`, so the parchment swatch stays
 *   parchment and the ink swatch stays ink whatever theme the page wears —
 *   they depict the target, not the current state.
 * - Autoren-Profil, the one dirty form (`profileForm.tsx`), with the two
 *   real addresses the user-block menu doors land on: `#profil-sektion`
 *   and `#tagesziel-feld` — a hash navigation focuses the field it names.
 * - The offline note, the draft's card, carried inside the profile section.
 *
 * W8 Task 9 adds exactly one thing to this page: the shared hub chrome
 * (`SettingsHub`, ruling 4) above the content — the content itself is
 * byte-stable, and the hub carries the two routes that exist.
 *
 * Honest states throughout: the loading skeleton while the strict read
 * stands, the outage face with its retry (the read is the settings
 * capability's own `useSettings` — a dressed-up null would be a lie here),
 * and the empty profile, where the email answers as the label — not an
 * error. The page imports no other capability (rule 1).
 */
import { useRouterState } from "@tanstack/react-router";
import { useEffect } from "react";

import { SettingsHub } from "@shell/components/SettingsHub";
import { endonyms, localeOrder } from "@shell/lib/generated/catalogs";
import { useTranslation } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import { useLanguageChoice } from "@shell/lib/language";
import { useSettings, useTheme } from "@shell/lib/query";
import { FOCUS } from "@shell/ui/card";

import { ProfileForm } from "./profileForm";
import { UpdatesSection } from "./UpdatesSection";

const SERIF = "[font-family:var(--font-serif)]";

/** The hash address table (the user block's doors and deep links): a
 *  section address names the field that answers it. A hash outside the
 *  table — or none — lands nowhere. */
const SECTION_FIELD: Record<string, string> = {
  "tagesziel-feld": "settings-daily-goal",
  "profil-sektion": "settings-author-name",
};

export function SettingsPage() {
  const t = useTranslation();
  usePageTitle(t("settings.heading"));
  const settings = useSettings();
  const { locale, chosen, choose } = useLanguageChoice();
  const { theme, setTheme } = useTheme();
  const hash = useRouterState({ select: (state) => state.location.hash });

  // The menu's addresses: a hash navigation (deep link or the user block's
  // doors) focuses the field it names once the row stands — the landing is
  // the field, not just a scroll. The map is the address table: a hash
  // that names no field (or no hash at all) lands nowhere, and the ids are
  // the fields' own.
  const ready = settings.isSuccess;
  useEffect(() => {
    if (!ready) return;
    const fieldId = SECTION_FIELD[hash];
    if (fieldId !== undefined) document.getElementById(fieldId)?.focus();
  }, [hash, ready]);

  // The theme cycle's states: the row's null is the system's own.
  const themeState = theme === "light" || theme === "dark" ? theme : "system";

  return (
    <main id="main-content" data-testid="settings-page" aria-busy={settings.isPending} className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl space-y-12 px-8 py-10 pb-24">
        {/* BEGIN: the settings hub chrome (W8 ruling 4) — the only change
            this page takes in PR 2: the content below is byte-stable. */}
        <SettingsHub />
        {/* END: the hub chrome. */}

        {/* Kopfzeile der Ansicht */}
        <div>
          <h1 className={`${SERIF} text-hero font-normal tracking-tight text-foreground`}>
            {t("settings.heading")}
          </h1>
          <p className="mt-1.5 max-w-xl text-meta leading-relaxed text-muted">{t("settings.subtitle")}</p>
        </div>

        {settings.isPending ? (
          /* The loading skeleton: the honest line, the draft's column. */
          <div className="space-y-6" role="status">
            <p className="text-body text-muted">{t("settings.loading")}</p>
            <div aria-hidden="true" className="space-y-3">
              <div className="h-8 w-56 animate-pulse rounded bg-soft" />
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div className="h-14 animate-pulse rounded bg-soft" />
                <div className="h-14 animate-pulse rounded bg-soft" />
                <div className="h-14 animate-pulse rounded bg-soft" />
              </div>
              <div className="h-40 animate-pulse rounded bg-soft" />
            </div>
          </div>
        ) : settings.isError ? (
          /* The outage: named, with the retry — never dressed-up nulls. */
          <div className="flex justify-center p-6">
            <div role="alert" className="space-y-2 rounded-lg border border-danger/40 bg-panel p-5 text-center">
              <p className="text-body text-danger">{t("settings.loadFailed")}</p>
              <button
                type="button"
                onClick={() => void settings.refetch()}
                className={`rounded border border-border bg-surface-container-low px-3 py-1.5 text-meta font-medium text-foreground transition-colors hover:bg-surface-container ${FOCUS}`}
              >
                {t("settings.retry")}
              </button>
            </div>
          </div>
        ) : (
          settings.data !== undefined && (
            <>
              {/* BEGIN: Sprache & Erscheinungsbild — the immediate section. */}
              <section aria-labelledby="settings-appearance-heading" className="space-y-6">
                <div className="border-b border-border pb-2.5">
                  <h2
                    id="settings-appearance-heading"
                    className={`${SERIF} text-title font-normal text-foreground`}
                  >
                    {t("settings.appearance.heading")}
                  </h2>
                  <p className="mt-0.5 text-meta text-muted">{t("settings.appearance.sub")}</p>
                </div>

                {/* Oberflächensprache — the contract's radios on the draft's
                    cards; the write is `choose`, the one language write. */}
                <div className="space-y-3">
                  <span className="block text-eyebrow font-semibold uppercase tracking-wider text-muted">
                    {t("settings.language.label")}
                  </span>
                  <div role="radiogroup" aria-label={t("settings.language.label")} className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                    {localeOrder.map((code) => {
                      const active = locale === code;
                      return (
                        <label
                          key={code}
                          className={`relative flex cursor-pointer items-center justify-between rounded-lg border bg-card p-3.5 transition-colors has-[:focus-visible]:outline-hidden has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-focus ${
                            active
                              ? "border-primary shadow-sm"
                              : "border-border hover:border-border hover:bg-panel"
                          }`}
                        >
                          <input
                            type="radio"
                            name="surface-language"
                            className="sr-only"
                            aria-label={endonyms[code]}
                            checked={active}
                            onChange={() => void choose(code)}
                          />
                          <span className="flex items-center gap-3">
                            <span
                              aria-hidden="true"
                              className={`flex h-4 w-4 items-center justify-center rounded-full border ${
                                active ? "border-primary" : "border-border"
                              }`}
                            >
                              {active && <span className="h-2 w-2 rounded-full bg-primary" />}
                            </span>
                            <span className={`text-body ${active ? "font-medium" : "font-normal"} text-foreground`}>
                              {endonyms[code]}
                            </span>
                          </span>
                          {active ? (
                            <span className="text-[11px] font-medium text-primary">
                              {t("settings.language.active")}
                            </span>
                          ) : (
                            <span className="text-[11px] text-muted">{code.toUpperCase()}</span>
                          )}
                        </label>
                      );
                    })}
                  </div>
                  {/* „Dem Browser folgen“ — the stored null, the seam's own
                      choice; the radio above marks the RESOLVED language. */}
                  <div className="flex flex-col justify-between gap-2 pt-1 text-meta text-muted sm:flex-row sm:items-center">
                    <label className="inline-flex cursor-pointer select-none items-center gap-2">
                      <input
                        type="checkbox"
                        className="h-4 w-4 accent-primary"
                        checked={chosen === null}
                        onChange={(event) => void choose(event.target.checked ? null : locale)}
                      />
                      <span className="text-foreground">{t("settings.language.followBrowser")}</span>
                    </label>
                    <span className="text-[11px] italic text-muted">{t("settings.language.instant")}</span>
                  </div>
                </div>

                {/* Farbton & Kontrast — the three appearance cards, the
                    shared theme write; the swatches depict their target
                    theme (pinned color-scheme), never the current one. */}
                <div className="space-y-3 pt-3">
                  <span className="block text-eyebrow font-semibold uppercase tracking-wider text-muted">
                    {t("settings.theme.label")}
                  </span>
                  <div role="radiogroup" aria-label={t("settings.theme.label")} className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                    {(
                      [
                        {
                          value: "light" as const,
                          label: t("settings.theme.light"),
                          sub: t("settings.theme.lightSub"),
                          swatch: (
                            <span className="flex items-center gap-1.5">
                              <span aria-hidden="true" className="inline-block h-3.5 w-5 rounded-sm border border-border bg-background [color-scheme:light]" />
                              <span aria-hidden="true" className="inline-block h-3.5 w-3.5 rounded-sm bg-primary [color-scheme:light]" />
                            </span>
                          ),
                        },
                        {
                          value: "dark" as const,
                          label: t("settings.theme.dark"),
                          sub: t("settings.theme.darkSub"),
                          swatch: (
                            <span className="flex items-center gap-1.5">
                              <span aria-hidden="true" className="inline-block h-3.5 w-5 rounded-sm border border-border bg-background [color-scheme:dark]" />
                              <span aria-hidden="true" className="inline-block h-3.5 w-3.5 rounded-sm bg-primary [color-scheme:dark]" />
                            </span>
                          ),
                        },
                        {
                          value: null,
                          label: t("settings.theme.system"),
                          sub: t("settings.theme.systemSub"),
                          swatch: (
                            <span aria-hidden="true" className="inline-flex h-3.5 w-5 overflow-hidden rounded-sm border border-border">
                              <span className="h-full w-1/2 bg-background [color-scheme:light]" />
                              <span className="h-full w-1/2 bg-background [color-scheme:dark]" />
                            </span>
                          ),
                        },
                      ] as const
                    ).map((card) => {
                      // The row's null is the system's own: the state names
                      // it, the write carries the null.
                      const active =
                        card.value === null ? themeState === "system" : themeState === card.value;
                      return (
                        <label
                          key={card.label}
                          className={`relative flex h-24 cursor-pointer flex-col justify-between rounded-lg border bg-card p-3.5 transition-colors has-[:focus-visible]:outline-hidden has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-focus ${
                            active ? "border-primary shadow-sm" : "border-border hover:bg-panel"
                          }`}
                        >
                          <input
                            type="radio"
                            name="surface-theme"
                            className="sr-only"
                            aria-label={card.label}
                            checked={active}
                            onChange={() => void setTheme(card.value)}
                          />
                          <span className="flex w-full items-center justify-between">
                            <span className={`text-meta ${active ? "font-medium" : "font-normal"} text-foreground`}>
                              {card.label}
                            </span>
                            <span
                              aria-hidden="true"
                              className={`flex h-3.5 w-3.5 items-center justify-center rounded-full border ${
                                active ? "border-primary" : "border-border"
                              }`}
                            >
                              {active && <span className="h-2 w-2 rounded-full bg-primary" />}
                            </span>
                          </span>
                          <span className="flex items-center justify-between pt-2">
                            {card.swatch}
                            <span className="text-[11px] italic text-muted" style={{ fontFamily: "var(--font-serif)" }}>
                              {card.sub}
                            </span>
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              </section>
              {/* END: Sprache & Erscheinungsbild */}

              {/* Autoren-Profil — the one dirty form, its section, the
                  offline note; `#profil-sektion` and `#tagesziel-feld`
                  live inside. */}
              <ProfileForm row={settings.data} />

              {/* The update check's interval — one small field beside the
                  profile form, the same row's write. */}
              <UpdatesSection row={settings.data} />
            </>
          )
        )}
      </div>
    </main>
  );
}
