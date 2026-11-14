import { Fragment, useId, useRef, type KeyboardEvent } from "react";

import { client } from "@shell/lib/api/client";
import { BookCover } from "@shell/lib/cover/BookCover";
import { catalogs } from "@shell/lib/generated/catalogs";
import { demos } from "@shell/lib/generated/demos";
import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import { activeLocale, applyLocale, chosenLocale, type Locale } from "@shell/lib/locale";
import { usePageTitle } from "@shell/lib/pageTitle";
import { queryClient, useNovelsQuery } from "@shell/lib/query";
import { Icon, type IconName } from "@shell/ui/icons";

import { storePreSetupLocale } from "./preSetupLocale";

/**
 * The post-setup landing — the `landing-atelier` draft ported 1:1 onto the
 * shell's tokens (spec §6.2), the `/` gate's complete branch. The hero speaks
 * the bound novel's own row (title, genre, chapter count) read through
 * `useNovelsQuery` — never session storage, never an invented progress: the
 * word stand is honestly „counted at your first writing" and the progress
 * track stands empty until there is something to measure.
 *
 * Every door the further build-out has not reached stays honestly disabled
 * with the drafted note „kommt mit dem weiteren Aufbau": the hero's three
 * actions, the three workroom cards (static, not controls) and the two
 * „Neues beginnen" doors. The demo list is a non-interactive roster that marks
 * the template the shelf holds by title match; the others wear their manifest
 * meta, not the draft's invented genre blurbs.
 *
 * The language switcher here is the post-setup contract: the settings row is
 * the record now, so a choice applies at once and PATCHes the row; a success
 * spends any leftover pre-setup mirror, a refusal restores the prior language.
 * There is no structural-409 branch — the row exists once setup has run.
 *
 * Deviations from the draft, kept honest (the gap doc records them): the
 * hand-drawn book object is the shared BookCover at size `hero`; the demo
 * seed's blockquote stays out (it is the archive's prose, not the reader's);
 * the tertiary CTA reads „Storyboard einsehen" without the draft's „3-Akt-"
 * prefix, which would claim a dramatic form the row does not carry; the
 * workroom cards drop the draft's hover affordance, which would imply a
 * clickability they do not have.
 *
 * Token mapping (the draft's hexes → the shell's roles): bg-panel-light →
 * panel, bg-card-light/surface-container-lowest → surface-container-lowest,
 * border-light → border, text-muted-light/on-surface-variant → muted,
 * primary-container → primary, state-success → success, cover-ink → cover-ink,
 * secondary-container → secondary-container.
 */

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The shell's focus ring on every control this page offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The draft draws DE|EN|FR with DE leading; the switcher keeps that order. */
const SWITCHER_ORDER: readonly Locale[] = ["de", "en", "fr"];

/** The three workrooms, in the draft's order — coming-soon cards, not doors.
 *  The Material concepts wear the app's own icon faces (spec §6.9). */
const ROOMS: readonly { icon: IconName; title: MessageKey; body: MessageKey }[] = [
  { icon: "focus", title: "setup.landing.room1.title", body: "setup.landing.room1.body" },
  { icon: "historyEdu", title: "setup.landing.room2.title", body: "setup.landing.room2.body" },
  { icon: "uploadFile", title: "setup.landing.room3.title", body: "setup.landing.room3.body" },
];

export function LandingPage() {
  // useTranslation subscribes to the locale store, so reading activeLocale in
  // render stays fresh across a switch — the welcome's same subscription.
  const t = useTranslation();
  const locale = activeLocale();
  const novels = useNovelsQuery();
  const heroNoteId = useId();
  const newNoteId = useId();
  const radioRefs = useRef<Partial<Record<Locale, HTMLButtonElement | null>>>({});
  usePageTitle(t("setup.landing"));

  /** Apply a locale and write the row — the post-setup contract. The row is
   *  the record now: a success spends any leftover pre-setup mirror and
   *  invalidates the cached row so the shell adopts the written choice; a
   *  refusal restores the prior language. No mirror write, no 409 branch. */
  async function choose(next: Locale) {
    if (next === activeLocale()) return;
    const previous = chosenLocale();
    applyLocale(next);
    try {
      const { response } = await client.PATCH("/api/settings", { body: { locale: next } });
      if (!response.ok) throw new Error(`refused: ${response.status}`);
      storePreSetupLocale(null);
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
    } catch {
      applyLocale(previous);
    }
  }

  /** The radio group's keyboard contract, the welcome's: arrows cycle and
   *  wrap, Home/End jump to the ends; the move selects and focuses, and the
   *  roving tabindex keeps the group one tab stop. */
  function radioKey(event: KeyboardEvent<HTMLButtonElement>, at: number) {
    const span = SWITCHER_ORDER.length;
    let next: number;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") next = (at + 1) % span;
    else if (event.key === "ArrowLeft" || event.key === "ArrowUp") next = (at - 1 + span) % span;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = span - 1;
    else return;
    event.preventDefault();
    const code = SWITCHER_ORDER[next];
    void choose(code);
    radioRefs.current[code]?.focus();
  }

  // The shelf is the one fact this page needs. While it is in flight the page
  // stays quiet; a failure surfaces to the root's error screen rather than
  // dressing an unreachable service up as a shelf; and a completed setup with
  // an empty shelf is a broken invariant, named as an error.
  if (novels.isPending) return null;
  if (novels.isError) throw novels.error;
  const novel = novels.data[0];
  if (novel === undefined) throw new Error("setup complete but the shelf holds no novel");

  return (
    // The draft's body: full-bleed, the footer pinned to the bottom of a tall
    // viewport. The shell owns the one <main> landmark; this is its content.
    <div className="flex min-h-screen w-full flex-col selection:bg-secondary-container selection:text-secondary-container-foreground">
      {/* 1. Header: monogram, wordmark & breadcrumb, engine pill, switcher */}
      <header className="sticky top-0 z-40 w-full border-b border-border bg-panel">
        <div className="mx-auto flex min-h-14 w-full max-w-7xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-6 py-2">
          <div className="flex items-center gap-3">
            <div className="flex h-7 w-7 items-center justify-center rounded border border-outline-variant bg-cover-ink shadow-sm">
              <span className={`${SERIF} text-title font-semibold leading-none text-surface-container-lowest`}>
                N
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className={`${SERIF} text-title font-semibold tracking-tight text-primary`}>
                {t("setup.welcome.wordmark")}
              </span>
              <span aria-hidden="true" className="text-meta text-muted">
                /
              </span>
              <span className="text-label font-medium text-muted">{t("setup.landing.breadcrumb")}</span>
            </div>
          </div>
          {/* The causality engine pill — a standing assurance, not a control */}
          <div className="hidden items-center gap-2 rounded-full border border-border bg-surface-container-low px-3 py-1 shadow-sm md:flex">
            <span aria-hidden="true" className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-success" />
            </span>
            <span className="text-meta tracking-wide text-muted">{t("setup.landing.engine")}</span>
          </div>
          <div className="flex items-center gap-4">
            <div className="hidden items-center rounded border border-border bg-surface-container-lowest px-2 py-0.5 text-meta text-muted sm:inline-flex">
              {t("setup.welcome.year")}
            </div>
            <div
              role="radiogroup"
              aria-label={t("setup.welcome.language")}
              className="flex items-center rounded border border-border bg-surface-container-low px-1 py-0.5 text-meta"
            >
              {SWITCHER_ORDER.map((code, at) => (
                <Fragment key={code}>
                  {at > 0 && (
                    <span aria-hidden="true" className="px-0.5 text-border">
                      |
                    </span>
                  )}
                  <button
                    type="button"
                    role="radio"
                    aria-label={catalogs[code]["locale.name"]}
                    aria-checked={code === locale}
                    tabIndex={code === locale ? 0 : -1}
                    ref={(node) => {
                      radioRefs.current[code] = node;
                    }}
                    onKeyDown={(event) => radioKey(event, at)}
                    onClick={() => void choose(code)}
                    className={
                      code === locale
                        ? `rounded bg-surface-container-lowest px-1.5 py-0.5 font-semibold text-primary shadow-sm ${FOCUS}`
                        : `rounded px-1.5 py-0.5 text-muted transition-colors hover:text-foreground ${FOCUS}`
                    }
                  >
                    {code.toUpperCase()}
                  </button>
                </Fragment>
              ))}
            </div>
            <div
              aria-hidden="true"
              className="flex h-7 w-7 items-center justify-center rounded-full border border-outline-variant bg-secondary-container text-meta font-semibold text-secondary-container-foreground"
            >
              AN
            </div>
          </div>
        </div>
      </header>

      {/* The main canvas */}
      <div className="mx-auto w-full max-w-7xl flex-1 space-y-12 px-6 py-8 md:py-10">
        {/* 2. Hero: the active work, the row's own facts */}
        <section className="relative overflow-hidden rounded-lg border border-border bg-surface-container-low p-6 shadow-sm sm:p-8 lg:p-10">
          <div aria-hidden="true" className="pointer-events-none absolute -bottom-10 -right-8 text-primary opacity-[0.03]">
            <Icon name="menuBook" size={400} />
          </div>
          <div className="relative z-10 grid grid-cols-1 items-center gap-8 lg:grid-cols-12 lg:gap-12">
            {/* The book object — the shared cover system at hero size */}
            <div className="flex justify-center lg:col-span-4 lg:justify-start">
              <BookCover title={novel.title} genre={novel.genre} author={novel.author} size="hero" />
            </div>
            <div className="space-y-5 lg:col-span-8">
              <div className="flex items-center gap-2">
                <span aria-hidden="true" className="inline-block h-2 w-2 rounded-full bg-success" />
                <span className="text-eyebrow uppercase tracking-wider text-success">
                  {t("setup.landing.eyebrow")}
                </span>
              </div>
              <div>
                <h1 className={`${SERIF} text-3xl font-bold tracking-tight text-primary sm:text-4xl`}>
                  {novel.title}
                </h1>
                <p className="mt-0.5 text-meta text-muted">
                  {novel.genre !== null
                    ? t("setup.landing.meta", { genre: novel.genre, count: novel.chapter_count })
                    : t("setup.basis.demoChapters", { count: novel.chapter_count })}
                </p>
              </div>
              {/* Honest progress: the track stands empty until there is a word
                  stand to measure — no invented percentage, no mock sliver. */}
              <div className="space-y-1.5 pt-1">
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-container-highest" />
                <div className="flex flex-col justify-between gap-1 text-meta text-muted sm:flex-row sm:items-center">
                  <span>{t("setup.landing.wordStand")}</span>
                  <span className="font-medium text-secondary">{t("setup.landing.progressRight")}</span>
                </div>
              </div>
              {/* The three actions — honestly not built yet */}
              <div className="flex flex-wrap items-center gap-3 pt-3">
                <button
                  type="button"
                  disabled
                  aria-describedby={heroNoteId}
                  className="inline-flex h-10 cursor-not-allowed items-center gap-2 rounded bg-primary px-5 text-emph font-semibold text-primary-foreground opacity-50 shadow-sm"
                >
                  <span>{t("setup.landing.cta.write")}</span>
                  <Icon name="arrowRight" size={16} />
                </button>
                <button
                  type="button"
                  disabled
                  aria-describedby={heroNoteId}
                  className="inline-flex h-10 cursor-not-allowed items-center gap-2 rounded border border-border bg-surface-container-lowest px-4 text-label text-foreground opacity-50 shadow-sm"
                >
                  <span className="text-secondary">
                    <Icon name="hub" size={18} />
                  </span>
                  <span>{t("setup.landing.cta.lore")}</span>
                </button>
                <button
                  type="button"
                  disabled
                  aria-describedby={heroNoteId}
                  className="inline-flex cursor-not-allowed items-center gap-1.5 rounded px-3 py-2 text-meta text-muted opacity-50"
                >
                  <Icon name="planning" size={16} />
                  <span>{t("setup.landing.cta.storyboard")}</span>
                </button>
              </div>
              <p id={heroNoteId} className="text-meta text-muted">
                {t("setup.welcome.comingSoon")}
              </p>
            </div>
          </div>
        </section>

        {/* 3. The three workrooms — coming-soon cards, not controls */}
        <section className="space-y-4">
          <div className="flex items-baseline justify-between border-b border-border pb-2">
            <h2 className={`${SERIF} text-title font-semibold text-primary`}>
              <span>{t("setup.landing.rooms.title")}</span>{" "}
              <span className="text-meta font-normal text-muted">{t("setup.landing.rooms.count")}</span>
            </h2>
            <span className="text-meta text-muted">{t("setup.landing.rooms.status")}</span>
          </div>
          <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
            {ROOMS.map((room) => (
              <div
                key={room.title}
                className="flex flex-col justify-between rounded border border-border bg-surface-container-low p-5"
              >
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex h-8 w-8 items-center justify-center rounded border border-border bg-surface-container-lowest text-secondary">
                      <Icon name={room.icon} size={18} />
                    </div>
                    <span className="rounded border border-border bg-surface-container px-2 py-0.5 text-meta text-muted">
                      {t("setup.landing.rooms.soon")}
                    </span>
                  </div>
                  <div>
                    <h3 className="text-emph text-foreground">{t(room.title)}</h3>
                    <p className="mt-1.5 text-body leading-relaxed text-muted">{t(room.body)}</p>
                  </div>
                </div>
                <div className="mt-4 border-t border-border/60 pt-4">
                  <span className="text-meta italic text-muted">{t("setup.welcome.comingSoon")}</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* 4. Begin something new — the two doors, honestly not yet */}
        <section className="space-y-4">
          <div className="flex items-baseline justify-between border-b border-border pb-2">
            <h2 className={`${SERIF} text-title font-semibold text-primary`}>
              {t("setup.landing.new.title")}
            </h2>
            <span className="text-meta text-muted">{t("setup.landing.new.status")}</span>
          </div>
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            {/* Card 1: open a new work — the wizard's door, not built yet */}
            <div className="flex flex-col justify-between rounded border border-border bg-surface-container-lowest p-6">
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded border border-border bg-surface-container-low text-primary">
                    <Icon name="plus" size={20} />
                  </div>
                  <div>
                    <h3 className="text-title text-primary">{t("setup.welcome.card1.title")}</h3>
                    <span className="text-meta text-secondary">{t("setup.landing.new.workMeta")}</span>
                  </div>
                </div>
                <p className="text-body leading-relaxed text-muted">{t("setup.landing.new.workBody")}</p>
              </div>
              <div className="mt-4 flex flex-col gap-1 border-t border-border pt-4">
                <button
                  type="button"
                  disabled
                  aria-describedby={newNoteId}
                  className="inline-flex cursor-not-allowed items-center gap-1 text-label font-medium text-primary opacity-50"
                >
                  <span>{t("setup.landing.new.workCta")}</span>
                  <Icon name="arrowRight" size={16} />
                </button>
                <span id={newNoteId} className="text-meta text-muted">
                  {t("setup.welcome.comingSoon")}
                </span>
              </div>
            </div>
            {/* Card 2: explore another template — the roster, not clickable */}
            <div className="flex flex-col justify-between rounded border border-border bg-surface-container-lowest p-6">
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded border border-border bg-surface-container-low text-secondary">
                    <Icon name="autoStories" size={20} />
                  </div>
                  <div>
                    <h3 className="text-title text-foreground">{t("setup.landing.new.demoTitle")}</h3>
                    <span className="text-meta text-muted">{t("setup.landing.new.demoMeta")}</span>
                  </div>
                </div>
                <ul className="divide-y divide-border/60 pt-1 text-body">
                  {demos.map((demo) => {
                    const active = demo.title === novel.title;
                    return (
                      <li key={demo.slug} className="flex items-center justify-between py-2">
                        <span className={active ? "font-medium text-foreground" : "text-muted"}>
                          {demo.title}
                        </span>
                        {active ? (
                          <span className="flex items-center gap-1 text-meta text-success">
                            <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-success" />
                            {t("setup.landing.new.demoActive")}
                          </span>
                        ) : (
                          <span className="text-meta text-secondary">
                            {t("setup.welcome.demoMeta", { genre: demo.genre, count: demo.chapters })}
                          </span>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
              <div className="mt-3 flex flex-col items-end gap-1 border-t border-border pt-3">
                <button
                  type="button"
                  disabled
                  aria-describedby={newNoteId}
                  className="inline-flex cursor-not-allowed items-center gap-1 text-meta text-secondary opacity-50"
                >
                  <span>{t("setup.landing.new.catalog")}</span>
                  <span aria-hidden="true">→</span>
                </button>
              </div>
            </div>
          </div>
        </section>
      </div>

      {/* 5. Footer: the quote, the divider, the trust bar & the engine line */}
      <footer className="mt-16 flex w-full flex-col items-center justify-between gap-5 border-t border-border bg-panel px-8 py-8 text-center">
        <figure className="mx-auto max-w-[34rem]">
          <blockquote className={`${SERIF} text-lg italic leading-relaxed text-primary`}>
            {t("setup.welcome.quote")}
          </blockquote>
          <figcaption className="mt-1 block text-meta text-muted">{t("setup.welcome.quoteSource")}</figcaption>
        </figure>
        <div aria-hidden="true" className="h-px w-16 bg-border" />
        <div className="flex w-full max-w-7xl flex-col items-center justify-between gap-3 pt-1 text-meta text-muted sm:flex-row">
          <div className="flex flex-wrap items-center justify-center gap-x-2 gap-y-1 sm:justify-start">
            <span className="font-medium text-primary">{t("setup.welcome.trust1.label")}</span>
            <span>{t("setup.welcome.trust1.note")}</span>
            <span aria-hidden="true" className="text-border">•</span>
            <span>{t("setup.welcome.trust2.label")}</span>
            <span aria-hidden="true" className="text-border">•</span>
            <span>{t("setup.welcome.trust3.label")}</span>
            <span>{t("setup.welcome.trust3.note")}</span>
          </div>
          <div className="text-xs tracking-wide text-muted">{t("setup.provisioning.footer.engine")}</div>
        </div>
      </footer>
    </div>
  );
}