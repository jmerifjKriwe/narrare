import { Link, useNavigate } from "@tanstack/react-router";
import { useRef, type KeyboardEvent } from "react";

import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import { Icon, type IconName } from "@shell/ui/icons";

import { WizardHeader } from "../WizardHeader";
import {
  DRAMATIC_FORMS,
  findDemo,
  useWizardState,
  type DramaticForm,
  type Typology,
} from "../wizardState";

/**
 * The wizard's second step — the `setup-step2-dramaturgie-struktur` draft
 * (five-form version) ported 1:1 onto the shell's tokens (spec §6.2). The
 * typology cards and the five paradigm cards are radio groups whose ids are
 * the backend registry's keys (`plotter|pantser|plantser`, the five dramatic
 * forms); the answers ride search params through `wizardState`, so a refresh
 * lands on the same choices and nothing is posted until step 4.
 *
 * The dead-signal condition is the draft's own: the three-act „In Dead Signal
 * vorkonfiguriert" hint and the plotter „Voreinstellung für Dead Signal" badge
 * appear only when the dead-signal demo is the chosen basis — the blank path
 * and every other demo stay neutral. Nothing is preselected: the address is
 * the only source of a selection, and continue stays honestly locked (no
 * error text — the draft shows none) until both a typology and a form stand.
 *
 * The basis banner names the chosen demo with the archive's facts (title,
 * genre, chapters) or stays honest and minimal on the blank path; the
 * preview's status line is the corrected draft's promise — „Echtzeit-Timeline
 * aktiv" — with no entity or node counts anywhere on this step.
 *
 * Token mapping (the draft's hexes → the shell's roles): surface-bright →
 * surface, pergament/pergament-card → surface-container-low, primary →
 * primary (the light half is the draft's #743B1F exactly), border-parchment →
 * border, border-parchment-strong → outline-variant, text-muted/on-surface-
 * variant → muted, state-success → success, secondary-container →
 * secondary-container. The tension curve is the draft's generic illustration
 * on every form — the registry's per-form beats are not setup data.
 */

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The shell's focus ring on every control this step offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The three typologies in the draft's order; ids are the registry's keys. */
const TYPOLOGY_DEFS: readonly {
  id: Typology;
  icon: IconName;
  label: MessageKey;
  body: MessageKey;
}[] = [
  {
    id: "plotter",
    icon: "schema",
    label: "setup.structure.typology.plotter.label",
    body: "setup.structure.typology.plotter.body",
  },
  {
    id: "pantser",
    icon: "search",
    label: "setup.structure.typology.pantser.label",
    body: "setup.structure.typology.pantser.body",
  },
  {
    id: "plantser",
    icon: "tune",
    label: "setup.structure.typology.plantser.label",
    body: "setup.structure.typology.plantser.body",
  },
];
const TYPOLOGY_ORDER: readonly Typology[] = TYPOLOGY_DEFS.map((def) => def.id);

/** The five paradigms in the draft's order; ids are the registry's keys. The
 *  three-act card carries the conditional demo hint instead of a count meta;
 *  the other four wear the draft's count line when not actively chosen. */
const FORM_DEFS: readonly {
  id: DramaticForm;
  icon: IconName;
  label: MessageKey;
  body: MessageKey;
  meta: MessageKey | null;
}[] = [
  {
    id: "three-act",
    icon: "insights",
    label: "setup.structure.form.threeAct.label",
    body: "setup.structure.form.threeAct.body",
    meta: null,
  },
  {
    id: "heros-journey",
    icon: "radar",
    label: "setup.structure.form.herosJourney.label",
    body: "setup.structure.form.herosJourney.body",
    meta: "setup.structure.form.herosJourney.meta",
  },
  {
    id: "seven-point",
    icon: "viewList",
    label: "setup.structure.form.sevenPoint.label",
    body: "setup.structure.form.sevenPoint.body",
    meta: "setup.structure.form.sevenPoint.meta",
  },
  {
    id: "five-act",
    icon: "gridView",
    label: "setup.structure.form.fiveAct.label",
    body: "setup.structure.form.fiveAct.body",
    meta: "setup.structure.form.fiveAct.meta",
  },
  {
    id: "save-the-cat",
    icon: "planning",
    label: "setup.structure.form.saveTheCat.label",
    body: "setup.structure.form.saveTheCat.body",
    meta: "setup.structure.form.saveTheCat.meta",
  },
];
const FORM_ORDER: readonly DramaticForm[] = FORM_DEFS.map((def) => def.id);

/** The draft's slider range and step — the blank path's live target seam. */
const WORDS_MIN = 30_000;
const WORDS_MAX = 130_000;
const WORDS_STEP = 5_000;

/** The preview scale's three bands — the draft's labels, live boundaries:
 *  below 50k the novella chip, below 100k the standard novel, above the epic. */
type PreviewBand = "novella" | "novel" | "epic";
function previewBand(words: number): PreviewBand {
  if (words < 50_000) return "novella";
  if (words < 100_000) return "novel";
  return "epic";
}
const PREVIEW_BANDS: Record<PreviewBand, MessageKey> = {
  novella: "setup.structure.preview.bandNovella",
  novel: "setup.structure.preview.bandNovel",
  epic: "setup.structure.preview.bandEpic",
};

/** The radio groups' keyboard contract, the welcome's: arrows cycle and wrap,
 *  Home/End jump to the ends, Space/Enter select; the move selects and focuses. */
function radioKey<T extends string>(
  event: KeyboardEvent<HTMLElement>,
  order: readonly T[],
  at: number,
  choose: (id: T) => void,
  refs: { current: Partial<Record<T, HTMLElement | null>> },
) {
  const span = order.length;
  let next: number;
  if (event.key === "ArrowRight" || event.key === "ArrowDown") next = (at + 1) % span;
  else if (event.key === "ArrowLeft" || event.key === "ArrowUp") next = (at - 1 + span) % span;
  else if (event.key === "Home") next = 0;
  else if (event.key === "End") next = span - 1;
  else if (event.key === " " || event.key === "Enter") next = at;
  else return;
  event.preventDefault();
  const id = order[next];
  choose(id);
  refs.current[id]?.focus();
}

export function StructureStep() {
  const t = useTranslation();
  const navigate = useNavigate();
  const { state, update } = useWizardState("/setup/structure");
  const demo = findDemo(state.demo);
  const deadSignal = demo?.slug === "dead-signal";
  const complete = state.typology !== null && state.form !== null;
  const typologyRefs = useRef<Partial<Record<Typology, HTMLElement | null>>>({});
  const formRefs = useRef<Partial<Record<DramaticForm, HTMLElement | null>>>({});
  usePageTitle(t("setup.structure"));

  const band = previewBand(state.targetWords);
  // The slider only speaks its own range; a target the first step committed
  // outside it stays visible in the display (the honest value) while the
  // thumb rests at the nearest end.
  const sliderValue = Math.min(WORDS_MAX, Math.max(WORDS_MIN, state.targetWords));

  return (
    // The draft's body: full-bleed, pinned ends, the selection pair in tokens.
    // The shell owns the one <main> landmark; this is its content.
    <div className="flex min-h-screen w-full flex-col justify-between selection:bg-secondary-container selection:text-secondary-container-foreground">
      {/* 1. Header & stepper — the wizard's shared chrome, step two active */}
      <WizardHeader activeStep={2} />

      {/* 2. The basis strip, the editorial intro, the two-column workspace */}
      <div className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-8 px-6 pb-12 pt-8">
        {/* The chosen basis — the archive's facts, or the honest blank line */}
        <div className="flex flex-col justify-between gap-3 rounded-xl border border-border bg-surface-container-low p-3.5 shadow-sm sm:flex-row sm:items-center sm:p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-success/40 bg-success/15 text-success">
              <Icon name="check" size={16} />
            </div>
            <div>
              <span className="block text-eyebrow uppercase tracking-wider text-muted">
                {t("setup.structure.banner.label")}
              </span>
              <div className="text-meta text-foreground">
                {demo !== null ? (
                  <>
                    {t("setup.structure.banner.demoLead")}{" "}
                    <span className={`${SERIF} text-body font-semibold italic text-primary`}>
                      {t("setup.structure.banner.demoTitle", { title: demo.title })}
                    </span>{" "}
                    <span>
                      {t("setup.structure.banner.demoMeta", { genre: demo.genre, count: demo.chapters })}
                    </span>{" "}
                    <span className="text-muted">{t("setup.structure.banner.note")}</span>
                  </>
                ) : (
                  <span>{t("setup.structure.banner.blank")}</span>
                )}
              </div>
            </div>
          </div>
          <div className="inline-flex items-center gap-1.5 self-start rounded-md border border-border bg-surface px-2.5 py-1 text-meta text-muted sm:self-auto">
            <span className="text-primary">
              <Icon name="shield" size={14} />
            </span>
            {t("setup.structure.banner.causality")}
          </div>
        </div>

        {/* Editorial intro */}
        <header className="max-w-3xl">
          <div className="mb-1.5 flex items-center gap-2 text-eyebrow uppercase tracking-widest">
            <span aria-hidden="true" className="h-px w-5 bg-primary" />
            <span className="text-primary">{t("setup.structure.eyebrow")}</span>
            <span aria-hidden="true" className="text-outline-variant">
              •
            </span>
            <span className="text-muted">{t("setup.structure.stepOf", { step: 2, total: 4 })}</span>
          </div>
          <h1
            className={`${SERIF} text-3xl font-normal leading-snug tracking-tight text-foreground sm:text-4xl`}
          >
            {t("setup.structure.heroTitle")}
          </h1>
          <p className={`${SERIF} mt-2 text-lg italic leading-relaxed text-muted`}>
            {t("setup.structure.heroBody")}
          </p>
        </header>

        <div className="grid grid-cols-1 items-start gap-8 lg:grid-cols-12">
          {/* LEFT: the mental model and the paradigm catalog (7 cols) */}
          <div className="flex flex-col gap-8 lg:col-span-7">
            {/* Section 1 — Autoren-Typologie */}
            <section className="flex flex-col gap-4 rounded-xl border border-border bg-surface-container-low p-5 shadow-sm sm:p-6">
              <div className="flex items-center justify-between gap-2 border-b border-rule pb-3">
                <div className="flex items-center gap-2">
                  <span className="text-primary">
                    <Icon name="person" size={20} />
                  </span>
                  <h2
                    id="structure-typology-title"
                    className={`${SERIF} text-title font-semibold tracking-tight text-foreground`}
                  >
                    {t("setup.structure.typology.title")}
                  </h2>
                </div>
                <span className="rounded bg-primary/10 px-2 py-0.5 text-eyebrow uppercase tracking-wider text-primary">
                  {t("setup.structure.typology.badge")}
                </span>
              </div>
              <p className="text-meta leading-relaxed text-muted">{t("setup.structure.typology.body")}</p>
              <div
                role="radiogroup"
                aria-labelledby="structure-typology-title"
                className="mt-1 grid grid-cols-1 gap-3.5"
              >
                {TYPOLOGY_DEFS.map((def, at) => {
                  const selected = state.typology === def.id;
                  return (
                    <div
                      key={def.id}
                      role="radio"
                      aria-checked={selected}
                      aria-labelledby={`typology-${def.id}-label`}
                      tabIndex={selected || (state.typology === null && at === 0) ? 0 : -1}
                      ref={(node) => {
                        typologyRefs.current[def.id] = node;
                      }}
                      onClick={() => update({ typology: def.id })}
                      onKeyDown={(event) =>
                        radioKey(event, TYPOLOGY_ORDER, at, (id) => update({ typology: id }), typologyRefs)
                      }
                      className={
                        selected
                          ? `flex cursor-pointer items-start gap-4 rounded-lg border-2 border-primary bg-surface p-4 shadow-sm transition-all ${FOCUS}`
                          : `flex cursor-pointer items-start gap-4 rounded-lg border border-border bg-surface-container-low p-4 transition-all hover:border-outline-variant ${FOCUS}`
                      }
                    >
                      {/* The draft's radio dot, drawn in tokens */}
                      <span
                        aria-hidden="true"
                        className={`mt-1 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border ${
                          selected ? "border-primary" : "border-outline-variant"
                        }`}
                      >
                        {selected && <span className="h-2 w-2 rounded-full bg-primary" />}
                      </span>
                      <span className="flex flex-1 flex-col gap-1">
                        <span className="flex items-center justify-between gap-2">
                          <span className="flex flex-wrap items-center gap-2">
                            <span
                              id={`typology-${def.id}-label`}
                              className="text-label font-semibold text-foreground"
                            >
                              {t(def.label)}
                            </span>
                            {def.id === "plotter" && deadSignal && (
                              <span className="rounded bg-secondary-container px-2 py-0.5 text-[10px] font-medium text-secondary-container-foreground">
                                {t("setup.structure.typology.plotter.badge")}
                              </span>
                            )}
                          </span>
                          <span className={selected ? "text-primary" : "text-muted"}>
                            <Icon name={def.icon} size={19} />
                          </span>
                        </span>
                        <span className="mt-0.5 text-meta leading-relaxed text-muted">{t(def.body)}</span>
                      </span>
                    </div>
                  );
                })}
              </div>
            </section>

            {/* Section 2 — Dramaturgische Form, the five paradigms */}
            <section className="flex flex-col gap-4 rounded-xl border border-border bg-surface-container-low p-5 shadow-sm sm:p-6">
              <div className="flex items-center justify-between gap-2 border-b border-rule pb-3">
                <div className="flex items-center gap-2">
                  <span className="text-primary">
                    <Icon name="hub" size={20} />
                  </span>
                  <h2
                    id="structure-form-title"
                    className={`${SERIF} text-title font-semibold tracking-tight text-foreground`}
                  >
                    {t("setup.structure.form.title")}
                  </h2>
                </div>
                <span className="rounded border border-border bg-surface-container px-2 py-0.5 text-meta font-medium text-muted">
                  {t("setup.structure.form.badge", { count: DRAMATIC_FORMS.length })}
                </span>
              </div>
              <div
                role="radiogroup"
                aria-labelledby="structure-form-title"
                className="grid grid-cols-1 gap-3.5 sm:grid-cols-2"
              >
                {FORM_DEFS.map((def, at) => {
                  const selected = state.form === def.id;
                  const threeAct = def.id === "three-act";
                  return (
                    <div
                      key={def.id}
                      role="radio"
                      aria-checked={selected}
                      aria-labelledby={`form-${def.id}-label`}
                      tabIndex={selected || (state.form === null && at === 0) ? 0 : -1}
                      ref={(node) => {
                        formRefs.current[def.id] = node;
                      }}
                      onClick={() => update({ form: def.id })}
                      onKeyDown={(event) =>
                        radioKey(event, FORM_ORDER, at, (id) => update({ form: id }), formRefs)
                      }
                      className={
                        (selected
                          ? `flex cursor-pointer flex-col justify-between gap-3 rounded-lg border-2 border-primary bg-surface p-4 shadow-sm transition-all ${FOCUS}`
                          : `flex cursor-pointer flex-col justify-between gap-3 rounded-lg border border-border bg-surface-container-low p-4 shadow-sm transition-all hover:border-outline-variant ${FOCUS}`) +
                        (def.id === "save-the-cat" ? " sm:col-span-2 md:col-span-1" : "")
                      }
                    >
                      <span className="flex items-start justify-between">
                        <span className="flex items-center gap-2">
                          <span
                            className={`flex h-8 w-8 items-center justify-center rounded border ${
                              selected
                                ? "border-primary/20 bg-primary/10 text-primary"
                                : "border-outline-variant bg-surface-container text-muted"
                            }`}
                          >
                            <Icon name={def.icon} size={18} />
                          </span>
                          {/* The three-act card's 3-bar pacing indicator */}
                          {threeAct && (
                            <span aria-hidden="true" className="flex h-4 items-end gap-0.5">
                              <span className={`h-2 w-1 rounded-xs ${selected ? "bg-primary" : "bg-outline-variant"}`} />
                              <span className={`h-3.5 w-1 rounded-xs ${selected ? "bg-primary" : "bg-outline-variant"}`} />
                              <span className={`h-2.5 w-1 rounded-xs ${selected ? "bg-primary" : "bg-outline-variant"}`} />
                            </span>
                          )}
                        </span>
                        <span
                          aria-hidden="true"
                          className={
                            selected
                              ? "flex h-5 w-5 items-center justify-center rounded-full bg-primary text-primary-foreground"
                              : "h-4 w-4 rounded-full border border-outline-variant"
                          }
                        >
                          {selected && <Icon name="check" size={13} />}
                        </span>
                      </span>
                      <span>
                        <span
                          id={`form-${def.id}-label`}
                          className="block text-label font-semibold text-foreground"
                        >
                          {t(def.label)}
                        </span>
                        <span className="mt-1 block text-meta leading-relaxed text-muted">
                          {t(def.body)}
                          {threeAct && deadSignal && (
                            <>
                              {" "}
                              <span>{t("setup.structure.form.threeAct.hint")}</span>
                            </>
                          )}
                        </span>
                      </span>
                      {selected ? (
                        <span className="flex items-center gap-1.5 text-meta font-medium uppercase tracking-wider text-primary">
                          <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-primary" />
                          {t("setup.structure.form.active")}
                        </span>
                      ) : def.meta !== null ? (
                        <span className="text-meta font-medium text-muted">{t(def.meta)}</span>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </section>
          </div>

          {/* RIGHT: the live preview — curve, target, the honest status (5 cols) */}
          <div className="flex flex-col gap-6 lg:col-span-5">
            <div className="relative flex flex-col gap-6 overflow-hidden rounded-xl border border-outline-variant bg-surface-container-low p-6 shadow-md">
              {/* Card header — the basis it previews */}
              <div className="flex items-start justify-between gap-2 border-b border-rule pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-primary" />
                    <span className="text-eyebrow uppercase tracking-wider text-muted">
                      {t("setup.structure.preview.eyebrow")}
                    </span>
                  </div>
                  <h3 className={`${SERIF} mt-0.5 text-2xl font-semibold text-foreground`}>
                    {demo !== null ? (
                      <>
                        {t("setup.structure.banner.demoLead")}{" "}
                        <span className="italic">
                          {t("setup.structure.banner.demoTitle", { title: demo.title })}
                        </span>
                      </>
                    ) : (
                      t("setup.structure.preview.blankTitle")
                    )}
                  </h3>
                </div>
                {demo !== null && (
                  <span className="rounded border border-secondary-container bg-secondary-container/60 px-2.5 py-1 text-meta font-semibold text-secondary-container-foreground">
                    {demo.genre}
                  </span>
                )}
              </div>

              {/* The tension curve — the draft's generic illustration, in tokens */}
              <div className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-4 shadow-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-eyebrow uppercase tracking-wider text-muted">
                    {t("setup.structure.preview.curveLabel")}
                  </span>
                  <span className="text-meta font-semibold text-primary">
                    {t("setup.structure.preview.curveClimax")}
                  </span>
                </div>
                <div className="relative h-24 w-full py-1">
                  <svg
                    aria-hidden="true"
                    className="h-full w-full text-primary"
                    fill="none"
                    preserveAspectRatio="none"
                    viewBox="0 0 360 85"
                  >
                    <line stroke="var(--color-outline-variant)" strokeDasharray="3 3" strokeWidth="1" x1="0" x2="360" y1="20" y2="20" />
                    <line stroke="var(--color-outline-variant)" strokeDasharray="3 3" strokeWidth="1" x1="0" x2="360" y1="50" y2="50" />
                    <path
                      d="M 0,65 Q 55,62 85,58 T 160,45 T 235,36 Q 275,10 295,8 Q 320,38 360,54 L 360,85 L 0,85 Z"
                      fill="currentColor"
                      fillOpacity="0.08"
                    />
                    <path
                      d="M 0,65 Q 55,62 85,58 T 160,45 T 235,36 Q 275,10 295,8 Q 320,38 360,54"
                      stroke="currentColor"
                      strokeLinecap="round"
                      strokeWidth="2.5"
                    />
                    <circle cx="20" cy="64" r="3.5" fill="currentColor" />
                    <circle cx="85" cy="58" r="4" fill="currentColor" />
                    <circle cx="160" cy="45" r="4" fill="currentColor" />
                    <circle cx="235" cy="36" r="4.5" fill="currentColor" />
                    <circle cx="295" cy="8" r="5.5" fill="currentColor" stroke="var(--color-surface)" strokeWidth="2" />
                    <circle cx="350" cy="52" r="3.5" fill="currentColor" />
                  </svg>
                </div>
                <div className="grid grid-cols-5 border-t border-rule/60 pt-1 text-center text-[9px] font-semibold uppercase tracking-wide text-muted sm:text-[10px] sm:tracking-wider">
                  <span className="text-left">{t("setup.structure.preview.beatExpos")}</span>
                  <span>{t("setup.structure.preview.beatInciting")}</span>
                  <span>{t("setup.structure.preview.beatMidpoint")}</span>
                  <span className="font-bold text-primary">{t("setup.structure.preview.beatClimax")}</span>
                  <span className="text-right">{t("setup.structure.preview.beatResolution")}</span>
                </div>
              </div>

              {/* The word target — live slider on the blank path, the committed
                  value read-only when a demo binds the step */}
              <div className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4 shadow-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="flex items-center gap-1.5 text-label font-semibold text-foreground">
                    <span className="text-primary">
                      <Icon name="write" size={17} />
                    </span>
                    {t("setup.structure.preview.wordsLabel")}
                  </span>
                  <span className={`${SERIF} text-lg font-semibold text-primary`}>
                    {t("setup.structure.preview.wordsDisplay", { count: state.targetWords })}
                  </span>
                </div>
                {demo === null && (
                  <input
                    type="range"
                    min={WORDS_MIN}
                    max={WORDS_MAX}
                    step={WORDS_STEP}
                    value={sliderValue}
                    aria-label={t("setup.structure.preview.wordsLabel")}
                    onChange={(event) => update({ targetWords: Number(event.target.value) })}
                    className={`h-2 w-full cursor-pointer accent-primary ${FOCUS}`}
                  />
                )}
                <div className="flex items-center justify-between gap-1 text-meta text-muted">
                  {(Object.keys(PREVIEW_BANDS) as PreviewBand[]).map((key) => (
                    <span
                      key={key}
                      className={
                        key === band
                          ? "rounded bg-surface-container px-2 py-0.5 font-semibold text-primary"
                          : undefined
                      }
                    >
                      {t(PREVIEW_BANDS[key])}
                    </span>
                  ))}
                </div>
                <div className="flex items-center gap-2 border-t border-rule/60 pt-2 text-meta text-success">
                  <Icon name="checkCircle" size={15} />
                  <span>{t("setup.structure.preview.sync")}</span>
                </div>
                {/* The corrected draft's honest status — no entity counts */}
                <div className="flex items-center gap-2 rounded border border-primary/20 bg-primary/5 px-2.5 py-1.5 text-meta text-primary">
                  <Icon name="historyEdu" size={15} />
                  <span className="font-medium">{t("setup.structure.preview.timeline")}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* 3. Wizard navigation — back keeps the state, continue needs both */}
        <div className="mt-4 flex w-full flex-col items-center justify-between gap-4 rounded-xl border border-border bg-surface-container-low p-4 shadow-sm sm:flex-row sm:p-5">
          <Link
            to="/setup/basis"
            search={true}
            className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-label font-medium text-foreground transition-colors hover:bg-surface-container hover:text-primary ${FOCUS}`}
          >
            <span className="rotate-180">
              <Icon name="arrowRight" size={18} />
            </span>
            <span>{t("setup.structure.back")}</span>
          </Link>
          <div className="flex w-full flex-col items-center justify-end gap-4 sm:w-auto sm:flex-row">
            <span className={`${SERIF} text-center text-meta italic text-muted sm:text-right`}>
              {complete
                ? t("setup.basis.status.configured", { step: 2, total: 4 })
                : t("setup.basis.status.incomplete", { step: 2, total: 4 })}
            </span>
            <button
              type="button"
              disabled={!complete}
              onClick={() => void navigate({ to: "/setup/ai-rules", search: true })}
              className={`group flex w-full items-center justify-center gap-2 rounded-lg px-5 py-2.5 text-label font-semibold tracking-wide shadow-sm transition-all sm:w-auto ${FOCUS} ${
                complete
                  ? "cursor-pointer bg-primary text-primary-foreground hover:opacity-95 hover:shadow"
                  : "cursor-not-allowed bg-surface-container-high text-muted shadow-none"
              }`}
            >
              <span>{t("setup.structure.continue")}</span>
              <span className="transition-transform group-hover:translate-x-0.5">
                <Icon name="arrowRight" size={18} />
              </span>
            </button>
          </div>
        </div>
      </div>

      {/* 4. The grounded literary footer */}
      <footer className="mt-auto w-full border-t border-border bg-surface-container-low py-4">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-2 px-6 text-meta text-muted sm:flex-row">
          <div className={`${SERIF} flex items-center gap-2 italic`}>
            <span>{t("setup.structure.footer.brand")}</span>
            <span aria-hidden="true">•</span>
            <span>{t("setup.structure.footer.tagline")}</span>
          </div>
          <div className="text-eyebrow uppercase tracking-widest text-muted/80">
            {t("setup.structure.footer.motto")}
          </div>
        </div>
      </footer>
    </div>
  );
}
