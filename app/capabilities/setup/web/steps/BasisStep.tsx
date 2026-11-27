import { Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useId, useRef, useState } from "react";

import { BookCover } from "@shell/lib/cover/BookCover";
import { channelFor, type CoverChannel } from "@shell/lib/cover/cover";
import { GenreMotif } from "@shell/lib/cover/motifs";
import { demos } from "@shell/lib/generated/demos";
import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import { activeLocale } from "@shell/lib/locale";
import { usePageTitle } from "@shell/lib/pageTitle";
import { Icon } from "@shell/ui/icons";

import { WizardHeader } from "../WizardHeader";
import {
  GENRE_CAP,
  GENRE_PILL_DEFS,
  TARGET_WORDS_MAX,
  basisComplete,
  demoDisplayTitle,
  findDemo,
  useWizardState,
  wouldOverflow,
} from "../wizardState";

/**
 * The wizard's first step — the `setup-step1-basis-vorlage` draft ported 1:1
 * onto the shell's tokens (spec §6.2), with the two state panels of
 * `setup-states-reference` wired in: panel 1's deterministic validation on
 * the blank path (the missing-title line, the locked continue) and panel 2's
 * binding on the demo path (title and genre locked to the archive, the lock
 * note, the selected-basis banner).
 *
 * The answers ride search params through `wizardState` — refresh-safe, and
 * nothing is posted until step 4. The live preview is the shared BookCover
 * at size `wizard`, fed by the title field (or the chosen demo's identity);
 * the genre pills join to the one ≤80-char string the backend contract
 * binds, and a pill whose addition would overflow is disabled with the
 * honest note instead of silently dropping the choice.
 *
 * Token mapping (the draft's hexes → the shell's roles): surface-bright →
 * surface, bg-card-light → surface-container-lowest, primary-container →
 * primary (the light half is the draft's #743B1F exactly), border-light →
 * border, rule-light → rule, outline-variant → outline-variant,
 * text-muted-light/on-surface-variant → muted, amber-focus → focus,
 * state-success → success, error-muted → danger. The demo mini-covers ride
 * the cover system's own literal ground/ink tokens (R2) with the hairline
 * GenreMotif where the draft drew Material glyphs; the invented series
 * subtitles and stat chips stay out — the archive's facts only.
 *
 * One contrast correction the E2E axe gate measures: the two chips on
 * surface-container-high (the option-A badge, the demo genre chips) ride
 * foreground ink — the draft drew on-surface-variant there, and muted, the
 * port's flattened ink, clears AA on the ground and the card only, not on
 * the raised rungs.
 */

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The shell's focus ring on every control this step offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The gauge's four format categories, in the draft's order. The boundaries
 *  are the draft's own bands; the widths and range labels are its gauge's. */
type Band = "short" | "novella" | "novel" | "epic";
const BAND_ORDER: readonly Band[] = ["short", "novella", "novel", "epic"];
const BANDS: Record<
  Band,
  { band: MessageKey; range: MessageKey; bar: MessageKey; width: string; dim: string }
> = {
  short: {
    band: "setup.basis.band.short",
    range: "setup.basis.range.short",
    bar: "setup.basis.bar.short",
    width: "w-[12%]",
    dim: "bg-outline-variant/50",
  },
  novella: {
    band: "setup.basis.band.novella",
    range: "setup.basis.range.novella",
    bar: "setup.basis.bar.novella",
    width: "w-[28%]",
    dim: "bg-outline-variant/80",
  },
  novel: {
    band: "setup.basis.band.novel",
    range: "setup.basis.range.novel",
    bar: "setup.basis.bar.novel",
    width: "w-[35%]",
    dim: "bg-outline-variant/60",
  },
  epic: {
    band: "setup.basis.band.epic",
    range: "setup.basis.range.epic",
    bar: "setup.basis.bar.epic",
    width: "w-[25%]",
    dim: "bg-outline-variant/60",
  },
};

/** The band a word target falls in — the draft's gauge boundaries. */
function wordBand(words: number): Band {
  if (words < 10_000) return "short";
  if (words < 50_000) return "novella";
  if (words < 100_000) return "novel";
  return "epic";
}

/** The Normseite's word count the draft's „240 Normseiten" at 65.000 implies. */
const WORDS_PER_NORMSEITE = 270;

/** R2: the mini-cover's ground/ink utilities per channel, literal so the
 *  scanner sees each — the same discipline BookCover keeps. The three demos
 *  land on scifi/fantasy/literary; the full record keeps any future demo on
 *  a pigment the cover system already owns. */
const MINI_PALETTE: Record<CoverChannel, { ground: string; ink: string }> = {
  scifi: { ground: "bg-cover-ink", ink: "text-cover-ink-ink" },
  fantasy: { ground: "bg-cover-fantasy", ink: "text-cover-fantasy-ink" },
  mystery: { ground: "bg-cover-pale", ink: "text-cover-pale-ink" },
  literary: { ground: "bg-cover-sepia", ink: "text-cover-sepia-ink" },
  historical: { ground: "bg-cover-slate", ink: "text-cover-slate-ink" },
  romance: { ground: "bg-cover-romance", ink: "text-cover-romance-ink" },
  thriller: { ground: "bg-cover-thriller", ink: "text-cover-thriller-ink" },
  fallback: { ground: "bg-cover-fallback", ink: "text-cover-fallback-ink" },
};

export function BasisStep() {
  const t = useTranslation();
  const navigate = useNavigate();
  const { state, update } = useWizardState("/setup/basis");
  const demo = findDemo(state.demo);
  const bound = demo !== null;
  // `useTranslation` above subscribes to the locale store, so this render-time
  // read follows a language switch; only the display title is localized.
  const locale = activeLocale();
  const complete = basisComplete(state);
  const titleMissing = !bound && state.title.trim() === "";
  const titleErrorId = useId();
  const genreLabelId = useId();
  const titleRef = useRef<HTMLInputElement | null>(null);
  const focusTitlePending = useRef(false);
  // The word field's draft while editing: a cleared or out-of-range entry
  // never reaches the state; on blur the field snaps back to the value that
  // would actually be sent, so it never shows a number the POST won't carry.
  const [wordsDraft, setWordsDraft] = useState<string | null>(null);
  // The title field's draft while editing, the same seam: the address drops a
  // whitespace-only title (empty-after-trim is a missing title), so without a
  // draft the round trip would eat a leading space the instant it is typed.
  // The draft holds exactly what the author typed; on blur the field snaps to
  // the value the address carries. Validation still reads the trimmed state.
  const [titleDraft, setTitleDraft] = useState<string | null>(null);
  usePageTitle(t("setup.basis"));

  // The binding's two seams: a bound step drops both drafts (the target and
  // the editable title belong to the blank path), and the tabula-rasa button's
  // focus request lands once the title field is editable again.
  useEffect(() => {
    if (bound) {
      setWordsDraft(null);
      setTitleDraft(null);
      return;
    }
    if (focusTitlePending.current) {
      focusTitlePending.current = false;
      titleRef.current?.focus();
    }
  }, [bound]);

  function togglePill(value: string) {
    update((prev) => ({
      genrePills: prev.genrePills.includes(value)
        ? prev.genrePills.filter((pill) => pill !== value)
        : [...prev.genrePills, value],
    }));
  }

  function changeWords(raw: string) {
    setWordsDraft(raw);
    const parsed = Number(raw);
    if (raw.trim() !== "" && Number.isInteger(parsed) && parsed >= 1 && parsed <= TARGET_WORDS_MAX) {
      update({ targetWords: parsed });
    }
  }

  /** The title's keystroke: the draft keeps the raw entry on screen while the
   *  address takes the serialized form (a whitespace-only title drops out). */
  function changeTitle(raw: string) {
    setTitleDraft(raw);
    update({ title: raw });
  }

  /** Option A's button: release any binding and hand focus to the title. */
  function startBlank() {
    if (bound) {
      focusTitlePending.current = true;
      update({ demo: null });
    } else {
      titleRef.current?.focus();
    }
  }

  const activeBand = wordBand(state.targetWords);
  const capBlocked = GENRE_PILL_DEFS.some(
    (pill) => !state.genrePills.includes(pill.value) && wouldOverflow(state.genrePills, pill.value),
  );
  const coverTitle = bound
    ? demoDisplayTitle(demo, locale)
    : state.title.trim() || t("setup.basis.coverUntitled");
  const coverGenre = bound ? demo.genre : (state.genrePills[0] ?? null);

  return (
    // The draft's body: full-bleed, pinned ends, the selection pair in tokens.
    // The shell owns the one <main> landmark; this is its content.
    <div className="flex min-h-screen w-full flex-col justify-between selection:bg-secondary-container selection:text-secondary-container-foreground">
      {/* 1. Header & stepper — the wizard's shared chrome, step one active */}
      <WizardHeader activeStep={1} />

      {/* 2. Title & hero */}
      <div className="mx-auto w-full max-w-7xl flex-1 px-6 pb-12 pt-8">
        <div className="mb-8 max-w-3xl">
          <div className="mb-2 flex items-center gap-2">
            <span aria-hidden="true" className="h-px w-5 bg-primary" />
            <span className="text-eyebrow uppercase tracking-widest text-primary">
              {t("setup.basis.eyebrow")}
            </span>
          </div>
          <h1
            className={`${SERIF} mb-2 text-3xl font-normal leading-tight tracking-tight text-foreground md:text-4xl`}
          >
            {t("setup.basis.heroTitle")}
          </h1>
          <p className={`${SERIF} text-lg leading-relaxed text-muted`}>{t("setup.basis.heroBody")}</p>
        </div>

        <div className="space-y-10">
          {/* 3a. Option A — the blank canvas */}
          <section className="rounded-xl border border-border bg-surface-container-lowest p-6 shadow-sm transition-all">
            <div className="flex flex-col justify-between gap-3 border-b border-rule pb-5 md:flex-row md:items-center">
              <div>
                <div className="mb-1 inline-flex items-center gap-1.5 rounded bg-surface-container-high px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-foreground">
                  <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-outline" />
                  {t("setup.basis.optionA.badge")}
                </div>
                <h2 className="text-title font-semibold text-foreground">{t("setup.basis.optionA.title")}</h2>
                <p className="mt-0.5 text-body text-muted">{t("setup.basis.optionA.body")}</p>
              </div>
              <button
                type="button"
                onClick={startBlank}
                className={`flex items-center gap-2 self-start rounded border border-border px-4 py-1.5 text-label text-foreground transition-colors hover:bg-surface-container-high md:self-auto ${FOCUS}`}
              >
                <Icon name="editNote" size={16} />
                <span>{t("setup.basis.optionA.cta")}</span>
              </button>
            </div>

            <div className="grid grid-cols-1 items-start gap-8 pt-6 lg:grid-cols-12">
              {/* Left: the form — or the bound fields when a demo stands */}
              <div className="space-y-6 lg:col-span-7">
                {/* Arbeitstitel — live on the blank path, locked on the demo path */}
                <div>
                  <div className="mb-1.5 flex items-center justify-between gap-2">
                    <label htmlFor="basis-title" className="text-label font-semibold text-foreground">
                      {bound ? t("setup.basis.boundTitle") : t("setup.basis.titleLabel")}
                      {!bound && (
                        <span aria-hidden="true" className="text-danger">
                          {" *"}
                        </span>
                      )}
                    </label>
                    {bound ? (
                      <span className="text-muted">
                        <Icon name="lock" size={11} />
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-meta italic text-primary">
                        <Icon name="historyEdu" size={14} />
                        {t("setup.basis.titleSync")}
                      </span>
                    )}
                  </div>
                  <div className="relative">
                    <input
                      id="basis-title"
                      ref={titleRef}
                      type="text"
                      disabled={bound}
                      required={!bound}
                      aria-invalid={titleMissing}
                      aria-describedby={titleMissing ? titleErrorId : undefined}
                      value={bound ? demoDisplayTitle(demo, locale) : (titleDraft ?? state.title)}
                      onChange={(event) => changeTitle(event.target.value)}
                      onBlur={() => setTitleDraft(null)}
                      placeholder={t("setup.basis.titlePlaceholder")}
                      className={`${SERIF} h-10 w-full rounded border bg-surface px-3.5 text-lg text-foreground outline-none transition-shadow focus:border-focus focus:ring-1 focus:ring-focus ${
                        titleMissing ? "border-danger pr-9" : "border-border"
                      } ${bound ? "cursor-not-allowed bg-surface-container-low text-muted" : ""}`}
                    />
                    {titleMissing && (
                      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-danger">
                        <Icon name="cross" size={14} />
                      </span>
                    )}
                  </div>
                  {titleMissing && (
                    <p
                      id={titleErrorId}
                      className={`${SERIF} flex items-start gap-1 pt-1 text-meta italic leading-tight text-danger`}
                    >
                      {t("setup.basis.titleError")}
                    </p>
                  )}
                </div>

                {bound ? (
                  <>
                    {/* Panel 2: the genre is the archive's, locked */}
                    <div>
                      <label
                        htmlFor="basis-genre-bound"
                        className="mb-1.5 flex items-center justify-between text-label font-semibold text-foreground"
                      >
                        <span>{t("setup.basis.boundGenre")}</span>
                        <span className="text-muted">
                          <Icon name="lock" size={11} />
                        </span>
                      </label>
                      <input
                        id="basis-genre-bound"
                        type="text"
                        disabled
                        value={demo.genre}
                        className="h-10 w-full cursor-not-allowed rounded border border-border bg-surface-container-low px-3.5 text-body text-muted"
                      />
                    </div>
                    {/* The binding's promise, panel 2's lock note */}
                    <div className="flex items-start gap-1.5 rounded border border-outline-variant/60 bg-surface-container-low/50 p-2 text-meta leading-snug text-primary">
                      <span className="mt-0.5 shrink-0">
                        <Icon name="lock" size={13} />
                      </span>
                      <span className={SERIF}>{t("setup.basis.lockNote")}</span>
                    </div>
                  </>
                ) : (
                  <>
                    {/* Genre pills — multi-select, joined to one string */}
                    <div>
                      <span id={genreLabelId} className="mb-2 block text-label font-semibold text-foreground">
                        {t("setup.basis.genreLabel")}
                      </span>
                      <div role="group" aria-labelledby={genreLabelId} className="flex flex-wrap gap-2">
                        {GENRE_PILL_DEFS.map((pill) => {
                          const selected = state.genrePills.includes(pill.value);
                          const blocked = !selected && wouldOverflow(state.genrePills, pill.value);
                          return (
                            <button
                              key={pill.value}
                              type="button"
                              aria-pressed={selected}
                              disabled={blocked}
                              onClick={() => togglePill(pill.value)}
                              className={
                                selected
                                  ? `flex items-center gap-1.5 rounded-full border border-primary bg-primary/10 px-3 py-1.5 text-label font-medium text-primary ${FOCUS}`
                                  : blocked
                                    ? "cursor-not-allowed rounded-full border border-border bg-surface px-3 py-1.5 text-label font-normal text-muted opacity-50"
                                    : `rounded-full border border-border bg-surface px-3 py-1.5 text-label font-normal text-muted transition-colors hover:bg-surface-container ${FOCUS}`
                              }
                            >
                              {selected && <Icon name="check" size={14} />}
                              {t(pill.key)}
                            </button>
                          );
                        })}
                      </div>
                      {capBlocked && (
                        <p className="mt-2 text-meta text-muted">
                          {t("setup.basis.genreCapNote", { cap: GENRE_CAP })}
                        </p>
                      )}
                    </div>

                    {/* Ziel-Umfang + the draft's format gauge — blank path only */}
                    <div className="flex flex-col items-center justify-between gap-4 rounded-lg border border-border bg-surface-container-low p-4 md:flex-row">
                      <div className="w-full space-y-1 md:w-auto">
                        <label htmlFor="basis-words" className="block text-label font-semibold text-foreground">
                          {t("setup.basis.wordsLabel")}
                        </label>
                        <div className="flex items-center gap-2">
                          <input
                            id="basis-words"
                            type="number"
                            inputMode="numeric"
                            min={1}
                            max={TARGET_WORDS_MAX}
                            value={wordsDraft ?? String(state.targetWords)}
                            onChange={(event) => changeWords(event.target.value)}
                            onBlur={() => setWordsDraft(null)}
                            className={`h-8 w-28 rounded border border-border bg-surface px-2.5 text-right text-emph text-foreground outline-none focus:border-focus ${FOCUS}`}
                          />
                          <span className="text-body text-muted">{t("setup.basis.wordsUnit")}</span>
                        </div>
                        <p className="text-meta text-muted">
                          {t("setup.basis.normseiten", {
                            count: Math.floor(state.targetWords / WORDS_PER_NORMSEITE),
                          })}
                        </p>
                      </div>
                      <div className="w-full rounded border border-border bg-surface p-3 md:w-64">
                        <div className="mb-1 flex items-center justify-between">
                          <span className="text-eyebrow font-semibold uppercase text-primary">
                            {t(BANDS[activeBand].band)}
                          </span>
                          <span className="text-meta font-medium text-foreground">
                            {t(BANDS[activeBand].range)}
                          </span>
                        </div>
                        <div className="flex h-2 w-full overflow-hidden rounded-full bg-surface-container">
                          {BAND_ORDER.map((band, at) => (
                            <div
                              key={band}
                              title={`${t(BANDS[band].band)} (${t(BANDS[band].range)})`}
                              className={`${BANDS[band].width} ${at > 0 ? "border-l border-surface-container-lowest" : ""} ${
                                band === activeBand ? "bg-primary" : BANDS[band].dim
                              }`}
                            />
                          ))}
                        </div>
                        <div className="mt-1 flex justify-between text-[9px] text-muted">
                          {BAND_ORDER.map((band) => (
                            <span
                              key={band}
                              className={band === activeBand ? "font-semibold text-primary" : ""}
                            >
                              {t(BANDS[band].bar)}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </>
                )}
              </div>

              {/* Right: the live book object — the shared cover, wizard size */}
              <div className="flex flex-col items-center justify-center p-4 lg:col-span-5">
                <span className="mb-3 text-eyebrow uppercase tracking-wider text-muted">
                  {t("setup.basis.coverEyebrow")}
                </span>
                <BookCover
                  title={coverTitle}
                  genre={coverGenre}
                  size="wizard"
                  className="transition-transform hover:scale-[1.01]"
                />
                <p className="mt-3 text-center text-meta text-muted">{t("setup.basis.coverCaption")}</p>
              </div>
            </div>
          </section>

          {/* 3b. Option B — the curated atelier, the three real demos */}
          <section className="rounded-xl border border-primary/30 bg-surface-container-low/60 p-6 shadow-sm">
            <div className="mb-6">
              <div className="mb-1 inline-flex items-center gap-1.5 rounded bg-primary px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-primary-foreground">
                <Icon name="autoStories" size={12} />
                {t("setup.basis.optionB.badge")}
              </div>
              <h2 className="text-title font-semibold text-foreground">{t("setup.basis.optionB.title")}</h2>
              <p className="mt-0.5 text-body text-muted">{t("setup.basis.optionB.body")}</p>
            </div>

            <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
              {demos.map((entry, at) => {
                const selected = state.demo === entry.slug;
                const channel = channelFor(entry.genre);
                const palette = MINI_PALETTE[channel];
                return (
                  <article
                    key={entry.slug}
                    id={`demo-${entry.slug}`}
                    className={
                      selected
                        ? "relative flex scroll-mt-24 flex-col justify-between rounded-lg border-2 border-primary bg-surface-container-lowest p-5 shadow-md transition-all"
                        : "group flex scroll-mt-24 flex-col justify-between rounded-lg border border-border bg-surface-container-lowest p-5 transition-all hover:border-outline-variant hover:shadow-md"
                    }
                  >
                    {selected && (
                      <div className="absolute -top-3 right-4 flex items-center gap-1 rounded bg-primary px-2.5 py-0.5 text-[11px] font-semibold text-primary-foreground shadow-sm">
                        <Icon name="checkCircle" size={13} />
                        {t("setup.basis.demoSelected")}
                      </div>
                    )}
                    <div>
                      {/* The mini cover — the channel's own ground and ink */}
                      <div
                        className={`relative mb-4 flex h-36 w-full flex-col justify-between overflow-hidden rounded border border-black/20 p-3 shadow-inner ${palette.ground} ${palette.ink}`}
                      >
                        <div className="flex items-center justify-between text-[9px] uppercase tracking-widest opacity-80">
                          <span>{t("setup.basis.demoEyebrow", { n: String(at + 1).padStart(2, "0") })}</span>
                          <GenreMotif channel={channel} className="size-4" />
                        </div>
                        <div className="my-auto text-left">
                          <div className={`${SERIF} text-lg italic leading-tight`}>
                            {demoDisplayTitle(entry, locale)}
                          </div>
                        </div>
                        <div className="flex justify-between text-[8px] uppercase tracking-wider opacity-80">
                          <span>{entry.genre}</span>
                          <span>{t("setup.basis.demoChapters", { count: entry.chapters })}</span>
                        </div>
                      </div>
                      {/* The archive's facts — title, genre, chapters */}
                      <div className="mb-3 space-y-1.5">
                        <div className="flex items-center justify-between gap-2">
                          <h3 className="text-emph font-bold text-foreground">
                            {demoDisplayTitle(entry, locale)}
                          </h3>
                          <span
                            className={`shrink-0 text-meta ${selected ? "font-semibold text-primary" : "text-muted"}`}
                          >
                            {t("setup.basis.demoChaptersWritten", { count: entry.chapters })}
                          </span>
                        </div>
                        <div className="inline-block rounded bg-surface-container-high px-2 py-0.5 text-[11px] font-medium text-foreground">
                          {entry.genre}
                        </div>
                      </div>
                      <p className={`${SERIF} mb-4 text-body leading-relaxed text-muted`}>„{entry.blurb}“</p>
                    </div>
                    <button
                      type="button"
                      aria-pressed={selected}
                      onClick={() => update({ demo: selected ? null : entry.slug })}
                      className={
                        selected
                          ? `flex h-8 w-full cursor-pointer items-center justify-center gap-1.5 rounded bg-primary text-label font-semibold text-primary-foreground transition-opacity hover:opacity-95 ${FOCUS}`
                          : `flex h-8 w-full cursor-pointer items-center justify-center rounded border border-border bg-surface-container-lowest text-label font-medium text-foreground transition-colors hover:bg-surface-container ${FOCUS}`
                      }
                    >
                      {selected && <Icon name="check" size={15} />}
                      {selected ? t("setup.basis.demoActive") : t("setup.basis.demoSelect")}
                    </button>
                  </article>
                );
              })}
            </div>

            <p className="mt-5 flex items-center justify-center gap-1.5 text-center text-meta text-muted">
              <span className="text-outline">
                <Icon name="lock" size={15} />
              </span>
              {t("setup.basis.bindingCaption")}
            </p>
          </section>

          {/* 4. The selected-basis banner — only when a demo stands */}
          {bound && (
            <aside className="flex flex-col items-center justify-between gap-3 rounded-lg border border-border bg-surface px-5 py-3.5 shadow-sm sm:flex-row">
              <div className="flex items-center gap-3">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-secondary-container text-primary">
                  <Icon name="bookmarkCollection" size={16} />
                </div>
                <div>
                  <div className="text-label font-semibold text-foreground">
                    {t("setup.basis.banner.title", { title: demoDisplayTitle(demo, locale) })}{" "}
                    <span className="font-normal text-muted">
                      {t("setup.basis.banner.meta", { genre: demo.genre, count: demo.chapters })}
                    </span>
                  </div>
                  <div className="text-meta text-muted">{t("setup.basis.banner.note")}</div>
                </div>
              </div>
              <a
                href={`#demo-${demo.slug}`}
                className={`flex items-center gap-1 whitespace-nowrap text-label font-semibold text-primary hover:underline ${FOCUS}`}
              >
                {t("setup.basis.banner.details")}
                <Icon name="arrowRight" size={14} />
              </a>
            </aside>
          )}
        </div>
      </div>

      {/* 5. Footer — cancel, the honest status, the primary continue */}
      <footer className="sticky bottom-0 z-30 w-full bg-surface shadow-[0_-4px_16px_rgba(0,0,0,0.03)]">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-6 py-3.5 sm:flex-row">
          <Link
            to="/"
            className={`flex w-full items-center justify-center gap-2 rounded px-3.5 py-1.5 text-label text-muted transition-colors hover:bg-surface-container hover:text-foreground sm:w-auto ${FOCUS}`}
          >
            <span className="rotate-180">
              <Icon name="arrowRight" size={18} />
            </span>
            <span>{t("setup.basis.cancel")}</span>
          </Link>
          <div className="flex items-center gap-1.5 text-center text-meta text-muted">
            <span
              aria-hidden="true"
              className={`h-2 w-2 rounded-full ${complete ? "bg-success" : "bg-outline-variant"}`}
            />
            <span>
              {complete
                ? t("setup.basis.status.configured", { step: 1, total: 4 })
                : t("setup.basis.status.incomplete", { step: 1, total: 4 })}
            </span>
          </div>
          <button
            type="button"
            disabled={!complete}
            onClick={() => void navigate({ to: "/setup/structure", search: true })}
            className={`group flex w-full items-center justify-center gap-2 rounded px-5 py-2 text-label font-semibold shadow-sm transition-colors duration-150 sm:w-auto ${FOCUS} ${
              complete
                ? "cursor-pointer bg-primary text-primary-foreground hover:opacity-95"
                : "cursor-not-allowed bg-surface-container-high text-muted shadow-none"
            }`}
          >
            <span>{t("setup.basis.continue")}</span>
            <span className="transition-transform group-hover:translate-x-0.5">
              <Icon name="arrowRight" size={16} />
            </span>
          </button>
        </div>
      </footer>
    </div>
  );
}
