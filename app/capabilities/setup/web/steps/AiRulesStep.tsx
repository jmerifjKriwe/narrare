import { Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useLayoutEffect, useRef, type KeyboardEvent } from "react";

import { client } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import { activeLocale, applyLocale, chosenLocale, type Locale } from "@shell/lib/locale";
import { usePageTitle } from "@shell/lib/pageTitle";
import { queryClient } from "@shell/lib/query";
import { Icon, type IconName } from "@shell/ui/icons";

import { readPreSetupLocale, storePreSetupLocale } from "../preSetupLocale";
import { useWizardState, type AiRole } from "../wizardState";

/**
 * The wizard's third step — the `setup-step3-ki-regeln-tonalitaet` draft
 * ported 1:1 onto the shell's tokens (spec §6.2). The four partner roles are
 * a radio group whose ids are the backend Literals (`archivar|lektor|coautor|
 * sparring`); the canon's strictness is a five-stop native range (1–5, the
 * backend's `canon_strictness` bounds) drawn as the draft's dot track but
 * driven by a real slider so the keyboard owns it. The answers ride search
 * params through `wizardState`, so a refresh lands on the same choices and
 * nothing is posted until step 4.
 *
 * Nothing is preselected: the address is the only source of a role, and
 * continue stays honestly locked (no error text — the draft shows none)
 * until a role stands. The canon, by contrast, opens at the balanced middle
 * stop (3) and that default is materialized into the address on arrival, so
 * the one POST always carries a strictness and only the role gates the door.
 * The draft's static „Empfohlen" badge stays on the lektor card (its own
 * recommendation, independent of the live selection); the draft's checked
 * lektor and its level-4 slider are its mock, not the live state.
 *
 * The audit card keeps the draft's neutral wording with no entity, station
 * or name examples and no invented binding metric; the draft's static
 * „92% Bindungsgrad" chip and the sovereignty ban-filter toggle (no backend
 * or seam field) stay out.
 *
 * Token mapping (the draft's hexes → the shell's roles): bg-panel-light →
 * panel, bg-card-light → surface-container-lowest, surface-container-low →
 * surface-container-low, primary-container → primary, border-light →
 * border, rule-light → rule, outline-variant → outline-variant,
 * text-muted-light/on-surface-variant → muted, state-success → success,
 * secondary-container → secondary-container, primary-fixed-dim → the
 * active dot's soft primary halo.
 */

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The shell's focus ring on every control this step offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The draft draws DE|EN|FR with DE leading; the switcher keeps that order. */
const SWITCHER_ORDER: readonly Locale[] = ["de", "en", "fr"];

/** The four roles in the draft's order; ids are the backend Literals. The
 *  lektor card wears the draft's standing recommendation badge. */
const ROLE_DEFS: readonly {
  id: AiRole;
  icon: IconName;
  metaIcon: IconName;
  label: MessageKey;
  body: MessageKey;
  meta: MessageKey;
  recommended?: boolean;
}[] = [
  {
    id: "archivar",
    icon: "bookmarkCollection",
    metaIcon: "clock",
    label: "setup.aiRules.role.archivar.label",
    body: "setup.aiRules.role.archivar.body",
    meta: "setup.aiRules.role.archivar.meta",
  },
  {
    id: "lektor",
    icon: "autoStories",
    metaIcon: "editNote",
    label: "setup.aiRules.role.lektor.label",
    body: "setup.aiRules.role.lektor.body",
    meta: "setup.aiRules.role.lektor.meta",
    recommended: true,
  },
  {
    id: "coautor",
    icon: "write",
    metaIcon: "clock",
    label: "setup.aiRules.role.coautor.label",
    body: "setup.aiRules.role.coautor.body",
    meta: "setup.aiRules.role.coautor.meta",
  },
  {
    id: "sparring",
    icon: "localFire",
    metaIcon: "waves",
    label: "setup.aiRules.role.sparring.label",
    body: "setup.aiRules.role.sparring.body",
    meta: "setup.aiRules.role.sparring.meta",
  },
];
const ROLE_ORDER: readonly AiRole[] = ROLE_DEFS.map((def) => def.id);

/** The canon's five stops and the balanced default the step opens at. */
const CANON_MIN = 1;
const CANON_MAX = 5;
const CANON_DEFAULT = 3;
const CANON_STOPS = [1, 2, 3, 4, 5] as const;

/** The three descriptive labels the draft sets under the track, at stops
 *  1, 3 and 5; the one nearest the live value wears the emphasis. */
const CANON_LABELS: readonly { at: number; label: MessageKey; note: MessageKey }[] = [
  { at: 1, label: "setup.aiRules.canon.tolerant", note: "setup.aiRules.canon.tolerantNote" },
  { at: 3, label: "setup.aiRules.canon.balanced", note: "setup.aiRules.canon.balancedNote" },
  { at: 5, label: "setup.aiRules.canon.strict", note: "setup.aiRules.canon.strictNote" },
];
function activeLabel(value: number): number {
  if (value < 2) return 1;
  if (value < 4) return 3;
  return 5;
}

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

export function AiRulesStep() {
  const t = useTranslation();
  const locale = activeLocale();
  const navigate = useNavigate();
  const { state, update } = useWizardState("/setup/ai-rules");
  const complete = state.aiRole !== null;
  const canon = state.canon ?? CANON_DEFAULT;
  const roleRefs = useRef<Partial<Record<AiRole, HTMLElement | null>>>({});
  const switcherRefs = useRef<Partial<Record<Locale, HTMLElement | null>>>({});
  usePageTitle(t("setup.aiRules"));

  // The pre-setup mirror, the welcome's contract: adopt before paint when
  // the settings row holds no choice yet.
  useLayoutEffect(() => {
    if (chosenLocale() !== null) return;
    const mirrored = readPreSetupLocale();
    if (mirrored !== null) applyLocale(mirrored);
  }, []);

  // The balanced default is a real answer: materialize it into the address
  // on arrival so the one POST always carries a strictness and a refresh or
  // a back/forward move lands on the same stop the slider shows.
  useEffect(() => {
    if (state.canon === null) update({ canon: CANON_DEFAULT });
  }, [state.canon, update]);

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

  /** The slider's keyboard contract: arrows step one stop and clamp at the
   *  ends, Home/End jump to them. Preventing the default keeps the native
   *  range from stepping twice; the move writes the address. */
  function canonKey(event: KeyboardEvent<HTMLInputElement>) {
    let next: number;
    if (event.key === "ArrowRight" || event.key === "ArrowUp") next = Math.min(CANON_MAX, canon + 1);
    else if (event.key === "ArrowLeft" || event.key === "ArrowDown") next = Math.max(CANON_MIN, canon - 1);
    else if (event.key === "Home") next = CANON_MIN;
    else if (event.key === "End") next = CANON_MAX;
    else return;
    event.preventDefault();
    update({ canon: next });
  }

  const emphasized = activeLabel(canon);

  return (
    // The draft's body: full-bleed, pinned ends, the selection pair in tokens.
    // The shell owns the one <main> landmark; this is its content.
    <div className="flex min-h-screen w-full flex-col justify-between selection:bg-secondary-container selection:text-secondary-container-foreground">
      {/* 1. Header & stepper — sticky, the wizard's shared chrome */}
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

          {/* Stepper — steps one and two done (the check, a way back), three active */}
          <nav
            aria-label={t("setup.wizard.progress")}
            className="hidden items-center gap-1 rounded-lg border border-border bg-surface-container-low px-3 py-1.5 md:flex"
          >
            {(["setup.wizard.step1", "setup.wizard.step2"] as const).map((key, at) => (
              <span key={key} className="flex items-center gap-1">
                {at > 0 && (
                  <span aria-hidden="true" className="px-1 text-meta text-outline-variant">
                    ›
                  </span>
                )}
                <Link
                  to={at === 0 ? "/setup/basis" : "/setup/structure"}
                  search={true}
                  className={`flex items-center gap-2 rounded px-2.5 py-1 text-label font-medium text-success transition-colors hover:bg-surface-container ${FOCUS}`}
                >
                  <Icon name="check" size={15} />
                  <span>{t(key)}</span>
                </Link>
              </span>
            ))}
            <span aria-hidden="true" className="px-1 text-meta text-outline-variant">
              ›
            </span>
            <div
              aria-current="step"
              className="flex items-center gap-2 rounded bg-primary px-2.5 py-1 text-label font-semibold text-primary-foreground shadow-sm"
            >
              <span aria-hidden="true" className="h-1.5 w-1.5 animate-pulse rounded-full bg-secondary-container" />
              <span>{t("setup.wizard.step3")}</span>
            </div>
            <span aria-hidden="true" className="px-1 text-meta text-outline-variant">
              ›
            </span>
            <span className="flex items-center gap-1.5 px-2 py-1 text-label text-muted">
              <span className="flex h-4 w-4 items-center justify-center rounded-full border border-outline-variant text-[10px]">
                4
              </span>
              <span>{t("setup.wizard.step4")}</span>
            </span>
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
                  onKeyDown={(event) =>
                    radioKey(event, SWITCHER_ORDER, at, (id) => void chooseLocale(id), switcherRefs)
                  }
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

      {/* 2. The editorial intro + guarantee seal, the two-column workspace */}
      <div className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-8 px-6 pb-12 pt-8">
        {/* Editorial intro with the causality guarantee seal */}
        <header className="flex flex-col justify-between gap-6 border-b border-border pb-6 md:flex-row md:items-end">
          <div className="max-w-2xl">
            <p className="mb-1.5 text-eyebrow uppercase tracking-widest text-primary">
              {t("setup.aiRules.eyebrow")}
            </p>
            <h1
              className={`${SERIF} text-3xl font-normal leading-snug tracking-tight text-primary sm:text-4xl`}
            >
              {t("setup.aiRules.heroTitle")}
            </h1>
            <p className={`${SERIF} mt-2 max-w-xl text-lg italic leading-relaxed text-muted`}>
              {t("setup.aiRules.heroBody")}
            </p>
          </div>
          {/* The guarantee seal — a standing assurance, not a control */}
          <div className="flex items-center gap-3 rounded-xl border border-border bg-panel p-3.5 shadow-sm">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-success/10 text-success">
              <Icon name="shield" size={20} />
            </div>
            <div>
              <div className="flex items-center gap-1 text-label font-semibold text-success">
                <span>{t("setup.aiRules.seal.title")}</span>
                <span aria-hidden="true" className="h-1.5 w-1.5 animate-pulse rounded-full bg-success" />
              </div>
              <p className="text-meta text-muted">{t("setup.aiRules.seal.body")}</p>
            </div>
          </div>
        </header>

        <div className="grid grid-cols-1 items-start gap-8 lg:grid-cols-12">
          {/* LEFT: the partner role & degree of interaction (7 cols) */}
          <section className="flex flex-col gap-4 lg:col-span-7">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-primary">
                  <Icon name="person" size={20} />
                </span>
                <h2
                  id="ai-rules-role-title"
                  className={`${SERIF} text-title font-semibold tracking-tight text-foreground`}
                >
                  {t("setup.aiRules.role.title")}
                </h2>
              </div>
              <span className="rounded-full border border-outline-variant/40 bg-secondary-container/60 px-2.5 py-0.5 text-meta font-medium text-secondary-container-foreground">
                {t("setup.aiRules.role.badge", { count: state.aiRole === null ? 0 : 1 })}
              </span>
            </div>
            <div
              role="radiogroup"
              aria-labelledby="ai-rules-role-title"
              className="grid grid-cols-1 gap-3.5 pt-1 md:grid-cols-2"
            >
              {ROLE_DEFS.map((def, at) => {
                const selected = state.aiRole === def.id;
                return (
                  <div
                    key={def.id}
                    role="radio"
                    aria-checked={selected}
                    aria-labelledby={`role-${def.id}-label`}
                    tabIndex={selected || (state.aiRole === null && at === 0) ? 0 : -1}
                    ref={(node) => {
                      roleRefs.current[def.id] = node;
                    }}
                    onClick={() => update({ aiRole: def.id })}
                    onKeyDown={(event) =>
                      radioKey(event, ROLE_ORDER, at, (id) => update({ aiRole: id }), roleRefs)
                    }
                    className={
                      selected
                        ? `relative flex cursor-pointer flex-col justify-between rounded-xl border-2 border-primary bg-surface-container-lowest p-4 shadow-sm ring-1 ring-primary/20 transition-all ${FOCUS}`
                        : `relative flex cursor-pointer flex-col justify-between rounded-xl border border-border bg-panel p-4 transition-all hover:border-outline-variant ${FOCUS}`
                    }
                  >
                    {def.recommended && (
                      <span className="absolute -top-2.5 right-3 rounded-full bg-primary px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-primary-foreground shadow-sm">
                        {t("setup.aiRules.role.recommended")}
                      </span>
                    )}
                    <span className="flex items-start justify-between gap-3">
                      <span
                        className={`flex h-8 w-8 items-center justify-center rounded-lg ${
                          selected ? "bg-secondary-container text-primary" : "bg-surface-container text-muted"
                        }`}
                      >
                        <Icon name={def.icon} size={18} />
                      </span>
                      {/* The draft's radio dot, drawn in tokens */}
                      <span
                        aria-hidden="true"
                        className={`mt-1 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border ${
                          selected ? "border-primary" : "border-outline-variant"
                        }`}
                      >
                        {selected && <span className="h-2 w-2 rounded-full bg-primary" />}
                      </span>
                    </span>
                    <span className="my-3">
                      <span
                        id={`role-${def.id}-label`}
                        className={`block text-emph ${selected ? "font-bold text-primary" : "font-semibold text-foreground"}`}
                      >
                        {t(def.label)}
                      </span>
                      <span className="mt-1.5 block text-meta leading-relaxed text-muted">
                        {t(def.body)}
                      </span>
                    </span>
                    <span
                      className={`flex items-center gap-1.5 border-t pt-3 text-meta ${
                        selected ? "border-secondary-container/50 font-medium text-primary" : "border-rule text-muted"
                      }`}
                    >
                      <Icon name={def.metaIcon} size={16} />
                      <span>{t(def.meta)}</span>
                    </span>
                  </div>
                );
              })}
            </div>
          </section>

          {/* RIGHT: canon strictness & the honest audit (5 cols) */}
          <div className="flex flex-col gap-6 lg:col-span-5">
            <section className="flex flex-col gap-5 rounded-2xl border border-border bg-panel p-5 shadow-sm">
              <div className="flex items-center justify-between border-b border-border pb-3">
                <div className="flex items-center gap-2">
                  <span className="text-primary">
                    <Icon name="hub" size={20} />
                  </span>
                  <h2
                    id="ai-rules-canon-title"
                    className={`${SERIF} text-title font-semibold tracking-tight text-foreground`}
                  >
                    {t("setup.aiRules.canon.title")}
                  </h2>
                </div>
                <span className="rounded bg-secondary-container px-2 py-0.5 text-label font-semibold text-primary">
                  {t("setup.aiRules.canon.badge", { n: canon })}
                </span>
              </div>

              {/* The five-stop slider: the draft's dot track, driven by a real
                  native range so pointer and keyboard both own it. */}
              <div className="flex flex-col gap-3">
                <div className="relative rounded-lg focus-within:ring-2 focus-within:ring-focus">
                  <div aria-hidden="true" className="relative flex h-8 items-center">
                    <div className="absolute left-3 right-3 h-1.5 rounded-full bg-surface-container-high" />
                    <div
                      className="absolute left-3 h-1.5 rounded-full bg-primary"
                      style={{ width: `calc((100% - 1.5rem) * ${(canon - 1) / 4})` }}
                    />
                    {CANON_STOPS.map((stop) => {
                      const active = stop === canon;
                      const filled = stop <= canon;
                      return (
                        <span
                          key={stop}
                          className={`absolute -translate-x-1/2 rounded-full ring-4 ${
                            active
                              ? "flex h-6 w-6 items-center justify-center bg-primary ring-primary/20"
                              : `h-4 w-4 ${filled ? "bg-primary" : "bg-surface-container-high"} ring-panel`
                          }`}
                          style={{ left: `calc(0.75rem + (100% - 1.5rem) * ${(stop - 1) / 4})` }}
                        >
                          {active && <span className="h-2 w-2 rounded-full bg-primary-foreground" />}
                        </span>
                      );
                    })}
                  </div>
                  <input
                    type="range"
                    min={CANON_MIN}
                    max={CANON_MAX}
                    step={1}
                    value={canon}
                    aria-label={t("setup.aiRules.canon.label")}
                    aria-valuetext={t("setup.aiRules.canon.badge", { n: canon })}
                    onChange={(event) => update({ canon: Number(event.target.value) })}
                    onKeyDown={canonKey}
                    className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
                  />
                </div>
                {/* The three descriptive stops, the nearest one emphasized */}
                <div className="flex justify-between pt-1 text-eyebrow text-muted">
                  {CANON_LABELS.map((stop, at) => (
                    <span
                      key={stop.at}
                      className={`w-1/3 ${at === 0 ? "text-left" : at === 1 ? "text-center" : "text-right"} ${
                        stop.at === emphasized ? "font-semibold text-primary" : ""
                      }`}
                    >
                      {t(stop.label)}
                      <br />
                      <span className="font-normal opacity-75">{t(stop.note)}</span>
                    </span>
                  ))}
                </div>
              </div>

              {/* The honest audit card — neutral wording, no invented metric */}
              <div className="flex items-start gap-3.5 rounded-xl border border-border bg-surface-container-low p-4">
                <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-success/15 text-success">
                  <Icon name="balance" size={20} />
                </div>
                <div className="flex flex-col gap-1">
                  <h3 className="text-emph text-foreground">{t("setup.aiRules.audit.title")}</h3>
                  <p className="text-meta leading-relaxed text-muted">{t("setup.aiRules.audit.body")}</p>
                </div>
              </div>
            </section>
          </div>
        </div>

        {/* 3. Wizard navigation — back keeps the state, continue needs a role */}
        <div className="mt-4 flex w-full flex-col items-center justify-between gap-4 rounded-xl border border-border bg-surface-container-low p-4 shadow-sm sm:flex-row sm:p-5">
          <Link
            to="/setup/structure"
            search={true}
            className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-label font-medium text-foreground transition-colors hover:bg-surface-container hover:text-primary ${FOCUS}`}
          >
            <span className="rotate-180">
              <Icon name="arrowRight" size={18} />
            </span>
            <span>{t("setup.aiRules.back")}</span>
          </Link>
          <div className="flex w-full flex-col items-center justify-end gap-4 sm:w-auto sm:flex-row">
            <span className={`${SERIF} text-center text-meta italic text-muted sm:text-right`}>
              {complete
                ? t("setup.basis.status.configured", { step: 3, total: 4 })
                : t("setup.basis.status.incomplete", { step: 3, total: 4 })}
            </span>
            <button
              type="button"
              disabled={!complete}
              onClick={() => void navigate({ to: "/setup/provisioning", search: true })}
              className={`group flex w-full items-center justify-center gap-2 rounded-lg px-5 py-2.5 text-label font-semibold tracking-wide shadow-sm transition-all sm:w-auto ${FOCUS} ${
                complete
                  ? "cursor-pointer bg-primary text-primary-foreground hover:opacity-95 hover:shadow"
                  : "cursor-not-allowed bg-surface-container-high text-muted shadow-none"
              }`}
            >
              <span>{t("setup.aiRules.continue")}</span>
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
