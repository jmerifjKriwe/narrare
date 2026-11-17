import { Link } from "@tanstack/react-router";
import { useId } from "react";

import { demos } from "@shell/lib/generated/demos";
import { useTranslation } from "@shell/lib/i18n";
import { LanguageSwitcher } from "@shell/lib/language";
import { usePageTitle } from "@shell/lib/pageTitle";
import { Icon } from "@shell/ui/icons";

/**
 * The welcome screen — the `welcome-atelier` draft ported 1:1 onto the
 * shell's tokens (spec §6.2): the emblem header with the language switcher,
 * the monumental serif hero, the three unhurried entries, the editorial
 * quote and the trust strip. The draft's literal hexes translate onto the
 * surface ladder (`#faf2ea` → surface-container-low, `#eee7df` →
 * surface-container-high, `#e4d9cc`/`#e8ded2` → border, `#d8c2b9` →
 * outline-variant); its secondary prose rides `text-muted`, the one ink the
 * contrast table gates on both the ground and the card. Two contrast
 * corrections the E2E axe gate measures: the card-2 meta chip rides
 * foreground ink on its high rung (the draft drew on-surface-variant there,
 * darker than muted — muted's AA contract does not cover the raised rungs),
 * and the engine line drops the draft's opacity-90, which dimmed muted below
 * AA on the ground. The drafts' Material Symbols keep their concepts and
 * wear the app's own faces (deviation #1, spec §6.9): stylus_note → editNote,
 * local_library → books, the rest named as in the draft.
 *
 * The three entries are real doors: the wizard starts at `/setup/basis`,
 * each demo row opens the wizard with its world preselected (`?demo=<slug>`,
 * the search param Task 5's basis step reads), and the import entry stays
 * honestly disabled — the manuscript import comes with the further
 * build-out, and the card says so instead of pretending. The language
 * switcher is the shared contract's welcome face (`@shell/lib/language`,
 * D17 / #892): it works before setup, when the settings row cannot hold a
 * choice yet — the mirror and the write's contract live in the one home.
 *
 * The composition is the draft's `main` — full-bleed, the footer pinned to
 * the bottom of a tall viewport — and the switcher is a radio group in the
 * draft's DE|EN|FR order. The copy stays selectable, the selection wearing
 * the draft body's own colours.
 */

/** The brand serif, the BookCover pattern: one stack, read from the token
 *  (R17). The draft's prose-heading and editorial faces are this voice. */
const SERIF = "[font-family:var(--font-serif)]";

/** The draft's focus affordance is the shell's ring: the keyboard's pointer
 *  in the one focus colour, on every door and switch this page offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The formats the import card names — file extensions, not copy. */
const FORMATS = [".docx", ".scriv", ".epub", ".md"] as const;

export function WelcomePage() {
  const t = useTranslation();
  const importNoteId = useId();
  usePageTitle(t("setup.welcome"));

  return (
    // The draft's `main`: full-bleed and pinned — header at the top, footer
    // at the bottom of a tall viewport, the grid spanning the whole breadth.
    // The copy stays selectable; the selection wears the draft's own colours
    // (its body's selection: pair), translated onto the shell's tokens.
    <div className="flex min-h-screen w-full flex-col justify-between p-4 selection:bg-secondary-container selection:text-secondary-container-foreground lg:p-8">
      {/* Top monograph emblem & ambient meta strip */}
      <header className="flex w-full flex-col items-center justify-between gap-4 pb-8 text-muted sm:flex-row">
        <div className="group flex cursor-default items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded border border-border bg-surface-container-high shadow-sm">
            <span className={`${SERIF} text-lg font-semibold italic tracking-tighter text-primary`}>
              N
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-eyebrow font-semibold uppercase tracking-widest text-foreground">
              {t("setup.welcome.wordmark")}
            </span>
            <span aria-hidden="true" className="text-outline-variant">
              •
            </span>
            <span className="text-meta">{t("setup.welcome.edition")}</span>
            <span aria-hidden="true" className="text-outline-variant">
              •
            </span>
            <span className="text-meta">{t("setup.welcome.year")}</span>
          </div>
        </div>
        <div className="flex items-center gap-6 text-meta">
          {/* The shared language contract's welcome face (D17 / #892): the
              draft's DE|EN|FR radio group, the pre-setup mirror contract. */}
          <LanguageSwitcher variant="welcome" preSetup />
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-success" />
            {t("setup.welcome.engine")}
          </span>
        </div>
      </header>

      {/* Monumental welcome header */}
      <div className="mx-auto flex w-full max-w-3xl flex-col items-center pb-8 pt-4 text-center">
        <span className="mb-3 text-eyebrow font-semibold uppercase tracking-widest text-primary">
          {t("setup.welcome.eyebrow")}
        </span>
        <h1
          className={`${SERIF} mb-4 text-4xl font-normal leading-tight tracking-tight text-foreground sm:text-5xl lg:text-6xl`}
        >
          {t("setup.welcome.heroTitle")}
        </h1>
        <p className={`${SERIF} max-w-2xl text-center text-lg leading-relaxed text-muted sm:text-xl`}>
          {t("setup.welcome.heroBody")}
        </p>
      </div>

      {/* Central interactive pathways — three unhurried choices */}
      <div className="my-6 grid w-full grid-cols-1 items-stretch gap-6 lg:grid-cols-3">
        {/* Card 1: open a new work — the wizard's door */}
        <div className="group relative flex flex-col justify-between overflow-hidden rounded-lg border border-border bg-surface-container-low p-6 shadow-sm transition-all duration-300 hover:shadow-md">
          <div aria-hidden="true" className="pointer-events-none absolute -bottom-6 -right-6 text-primary opacity-5">
            <Icon name="autoStories" size={170} />
          </div>
          <div className="relative z-10 flex flex-col">
            {/* gap guards the longer locales: the draft's row fits German
                without one, but a wrapped badge must never touch the meta. */}
            <div className="mb-4 flex items-center justify-between gap-2">
              <span className="inline-flex items-center gap-1 rounded bg-primary/10 px-2.5 py-0.5 text-eyebrow font-semibold text-primary">
                {t("setup.welcome.card1.badge")}
              </span>
              <span className="text-meta tabular-nums text-muted">{t("setup.welcome.card1.meta")}</span>
            </div>
            <div className="mb-4 flex h-10 w-10 items-center justify-center rounded border border-border bg-surface text-primary shadow-sm">
              <Icon name="editNote" size={24} />
            </div>
            <h2 className={`${SERIF} mb-2 text-2xl font-semibold text-foreground`}>
              {t("setup.welcome.card1.title")}
            </h2>
            <p className="mb-4 text-body leading-relaxed text-muted">{t("setup.welcome.card1.body")}</p>
            <div className="mb-2 rounded border border-border/60 bg-surface/70 px-3 py-2">
              <span className="flex items-center gap-1.5 text-meta text-muted">
                <span className="text-primary">
                  <Icon name="checkCircle" size={14} />
                </span>
                {t("setup.welcome.card1.note")}
              </span>
            </div>
          </div>
          <div className="relative z-10 mt-auto border-t border-border/60 pt-4">
            <Link
              to="/setup/basis"
              className={`inline-flex w-full cursor-pointer items-center justify-center gap-2 rounded bg-primary px-4 py-2.5 text-label font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 active:scale-[0.99] ${FOCUS}`}
            >
              <span>{t("setup.welcome.card1.cta")}</span>
              <Icon name="arrowRight" size={14} />
            </Link>
          </div>
        </div>

        {/* Card 2: explore a curated world — the three real demos */}
        <div className="group flex flex-col justify-between rounded-lg border border-border bg-surface p-6 shadow-sm transition-all duration-300 hover:shadow-md">
          <div className="flex flex-col">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex h-10 w-10 items-center justify-center rounded border border-border bg-surface-container text-primary">
                <Icon name="books" size={20} />
              </div>
              <span className="rounded bg-surface-container-high px-2 py-0.5 text-meta font-medium text-foreground">
                {t("setup.welcome.card2.meta")}
              </span>
            </div>
            <h2 className={`${SERIF} mb-1 text-2xl font-semibold text-foreground`}>
              {t("setup.welcome.card2.title")}
            </h2>
            <p className="mb-3 text-xs text-muted">{t("setup.welcome.card2.body")}</p>
            <div className="my-1 flex flex-col gap-2.5">
              {demos.map((demo) => (
                <Link
                  key={demo.slug}
                  to="/setup/basis"
                  search={{ demo: demo.slug }}
                  className={`block rounded border border-border bg-surface-container-low p-2.5 transition-colors hover:border-primary/40 ${FOCUS}`}
                >
                  <span className="mb-1 flex items-center justify-between gap-2">
                    <span className={`${SERIF} text-sm font-semibold italic text-foreground`}>
                      »{demo.title}«
                    </span>
                    <span className="shrink-0 text-[11px] text-muted">
                      {t("setup.welcome.demoMeta", { genre: demo.genre, count: demo.chapters })}
                    </span>
                  </span>
                </Link>
              ))}
            </div>
          </div>
          <div className="mt-4 flex items-center justify-between border-t border-border/60 pt-4">
            {/* The footer CTA follows the first demo — the card's own lead. */}
            <Link
              to="/setup/basis"
              search={{ demo: demos[0].slug }}
              className={`inline-flex cursor-pointer items-center gap-1.5 text-label font-medium text-primary transition-transform hover:underline group-hover:translate-x-0.5 ${FOCUS}`}
            >
              <span>{t("setup.welcome.card2.cta")}</span>
              <Icon name="arrowRight" size={14} />
            </Link>
            <div aria-hidden="true" className="flex -space-x-1.5 opacity-80">
              <span className="inline-block h-4 w-4 rounded-full bg-primary shadow-xs" />
              <span className="inline-block h-4 w-4 rounded-full bg-secondary-container shadow-xs" />
              <span className="inline-block h-4 w-4 rounded-full bg-surface-container-highest shadow-xs" />
            </div>
          </div>
        </div>

        {/* Card 3: bring an existing manuscript — honestly not yet */}
        <div className="group flex flex-col justify-between rounded-lg border border-border bg-surface p-6 shadow-sm transition-all duration-300 hover:shadow-md">
          <div className="flex flex-col">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex h-10 w-10 items-center justify-center rounded border border-border bg-surface-container text-primary">
                <Icon name="uploadFile" size={20} />
              </div>
              <div className="flex items-center gap-1">
                {FORMATS.map((format) => (
                  <span
                    key={format}
                    className="rounded bg-surface-container px-1.5 py-0.5 font-mono text-[11px] text-muted"
                  >
                    {format}
                  </span>
                ))}
              </div>
            </div>
            <h2 className={`${SERIF} mb-2 text-2xl font-semibold text-foreground`}>
              {t("setup.welcome.card3.title")}
            </h2>
            <p className="mb-4 text-body leading-relaxed text-muted">{t("setup.welcome.card3.body")}</p>
            <div className="mb-2 flex flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed border-outline-variant bg-surface-container-low/60 p-4 py-6 text-center">
              <span className="text-secondary">
                <Icon name="cloudUpload" size={24} />
              </span>
              <span className="text-meta font-medium text-foreground">{t("setup.welcome.card3.drop")}</span>
              <span className="text-[11px] text-muted">{t("setup.welcome.card3.dropNote")}</span>
            </div>
          </div>
          <div className="mt-auto flex items-center justify-between border-t border-border/60 pt-4">
            <div className="flex flex-col gap-1">
              <button
                type="button"
                disabled
                aria-describedby={importNoteId}
                className="inline-flex cursor-not-allowed items-center gap-1.5 text-label font-medium text-primary opacity-50"
              >
                <span>{t("setup.welcome.card3.cta")}</span>
                <Icon name="arrowRight" size={14} />
              </button>
              <span id={importNoteId} className="text-meta text-muted">
                {t("setup.welcome.comingSoon")}
              </span>
            </div>
            <span className="text-muted">
              <Icon name="document" size={16} />
            </span>
          </div>
        </div>
      </div>

      {/* Quiet editorial quote / tone anchor */}
      <figure className="mx-auto my-6 max-w-xl py-2 text-center">
        <blockquote className={`${SERIF} text-lg italic leading-relaxed text-foreground`}>
          {t("setup.welcome.quote")}
        </blockquote>
        <figcaption className="mt-1 text-meta text-muted">{t("setup.welcome.quoteSource")}</figcaption>
      </figure>

      {/* Bottom serene trust & philosophy strip */}
      <footer className="mt-4 flex w-full flex-col items-center justify-between gap-4 rounded-lg bg-surface-container/60 p-4 md:flex-row">
        <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-center md:justify-start md:text-left">
          <div className="flex items-center gap-2">
            <span className="text-primary">
              <Icon name="lock" size={16} />
            </span>
            <span className="text-body font-medium text-foreground">{t("setup.welcome.trust1.label")}</span>
            <span className="hidden text-meta text-muted sm:inline">{t("setup.welcome.trust1.note")}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-primary">
              <Icon name="balance" size={16} />
            </span>
            <span className="text-body font-medium text-foreground">{t("setup.welcome.trust2.label")}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-primary">
              <Icon name="shield" size={16} />
            </span>
            <span className="text-body font-medium text-foreground">{t("setup.welcome.trust3.label")}</span>
            <span className="hidden text-meta text-muted sm:inline">{t("setup.welcome.trust3.note")}</span>
          </div>
        </div>
        <a
          href="#handbuch"
          className={`inline-flex items-center gap-1 whitespace-nowrap text-meta font-medium text-primary hover:underline ${FOCUS}`}
        >
          <span>{t("setup.welcome.trustLink")}</span>
          <Icon name="openInNew" size={12} />
        </a>
      </footer>
    </div>
  );
}
