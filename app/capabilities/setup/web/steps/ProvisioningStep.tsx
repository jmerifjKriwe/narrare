import { Link, useNavigate } from "@tanstack/react-router";
import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";

import { client, type SetupResult } from "@shell/lib/api/client";
import { BookCover } from "@shell/lib/cover/BookCover";
import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import { activeLocale } from "@shell/lib/locale";
import { usePageTitle } from "@shell/lib/pageTitle";
import { queryClient } from "@shell/lib/query";
import { Icon } from "@shell/ui/icons";

import { readPreSetupLocale, storePreSetupLocale } from "@shell/lib/preSetupLocale";
import { useSetupStatus } from "../useSetupStatus";
import { WizardHeader } from "../WizardHeader";
import {
  basisComplete,
  demoDisplayTitle,
  findDemo,
  joinGenres,
  useWizardState,
  type AiRole,
  type DramaticForm,
} from "../wizardState";

/**
 * The wizard's fourth step — the `setup-step4-bereitstellung-start` draft
 * ported 1:1 onto the shell's tokens (spec §6.2), with the two async panels
 * of `setup-states-reference` wired in: panel 3's binding checklist while the
 * one POST is in flight, and panel 4's honest failure card when it is refused.
 * This is the only step that writes: it posts the accumulated answers once,
 * and the checklist it renders afterwards is exactly the SetupResult's facts
 * — the effective genre, the localized form and role labels, the chapter
 * count the import/creation produced — never an invented number.
 *
 * The POST body is the wizardState at the address boundary: the title is
 * trimmed here (the address keeps the raw string a refresh would land on),
 * the demo path posts the archive's slug and title with no genre beside it,
 * the blank path joins the genre pills into the one ≤80-char string, and the
 * target always rides along. A 409 means the instance is already complete —
 * the step invalidates the status and the shelf and routes to the landing,
 * never re-posting. The effect is ref-guarded so StrictMode's double mount
 * still posts exactly once.
 *
 * The locale seam lives here: once the POST lands and the settings row
 * exists, the pre-setup mirror is carried into it with a PATCH, then cleared.
 * A refused carry-over keeps the mirror (the wizard still speaks it) and a
 * seam failure never flips the bound phase — the book is bound either way.
 *
 * Deviations from the drafts, kept honest (the gap doc records them): the
 * hand-drawn book object is the shared BookCover at size `hero`; panel 4's
 * stopped checklist with its false check marks stays out because the POST is
 * atomic (nothing is half-bound); the binding progress bar carries no
 * percentage, and the bound face's „Bereit (100 %)" is the draft's own
 * completion label, not a measured metric. Two contrast corrections the E2E
 * axe gate measures: the context pill rides foreground ink on its highest
 * rung (the draft drew on-surface-variant; muted clears AA on the ground and
 * the card only), and the waiting checklist rows drop the draft's opacity-45
 * — the waiting face is the numbered ring and the mono „ausstehend", not
 * unreadable text.
 *
 * Token mapping (the draft's hexes → the shell's roles): bg-card-light →
 * surface-container-lowest, border-light → border, rule-light → rule,
 * outline-variant → outline-variant, text-muted-light/on-surface-variant →
 * muted, state-success → success, state-danger → danger, primary-container →
 * primary, surface-container-high → surface-container-high.
 */

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The shell's focus ring on every control this step offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The three faces the step moves through: the POST in flight, the bound
 *  checklist, the refused binding. */
type Phase = "binding" | "bound" | "failed";

/** Why a binding failed: the service unreachable, or an HTTP refusal whose
 *  status the cause line names. */
type Cause = { kind: "network" } | { kind: "status"; status: number };

/** The five dramatic forms → their localized labels, the structure step's
 *  own keys. The ids are the backend Literals. */
const FORM_LABELS: Record<DramaticForm, MessageKey> = {
  "three-act": "setup.structure.form.threeAct.label",
  "heros-journey": "setup.structure.form.herosJourney.label",
  "save-the-cat": "setup.structure.form.saveTheCat.label",
  "five-act": "setup.structure.form.fiveAct.label",
  "seven-point": "setup.structure.form.sevenPoint.label",
};

/** The four partner roles → their localized labels, the AI-rules step's own
 *  keys. The ids are the backend Literals. */
const ROLE_LABELS: Record<AiRole, MessageKey> = {
  archivar: "setup.aiRules.role.archivar.label",
  lektor: "setup.aiRules.role.lektor.label",
  coautor: "setup.aiRules.role.coautor.label",
  sparring: "setup.aiRules.role.sparring.label",
};

/** A nullable result id → its localized label, or null when the answer is
 *  absent or unknown — the checklist answers with a dash, never a guess. */
function formLabel(id: string | null): MessageKey | null {
  return id !== null && id in FORM_LABELS ? FORM_LABELS[id as DramaticForm] : null;
}
function roleLabel(id: string | null): MessageKey | null {
  return id !== null && id in ROLE_LABELS ? ROLE_LABELS[id as AiRole] : null;
}

export function ProvisioningStep() {
  const t = useTranslation();
  const navigate = useNavigate();
  const { state } = useWizardState("/setup/provisioning");
  // `useTranslation` subscribes to the locale store, so this render-time read
  // follows a language switch; the POST below still binds the archive's title.
  const locale = activeLocale();
  // The status query suspends before any early return: a direct entry asks
  // it once, and the 409's invalidation refetches it while this step still
  // observes — the `/` gate then reads the fresh complete answer.
  useSetupStatus();
  const [phase, setPhase] = useState<Phase>("binding");
  const [result, setResult] = useState<SetupResult | null>(null);
  const [cause, setCause] = useState<Cause | null>(null);
  const postedRef = useRef(false);
  const noteId = useId();
  usePageTitle(t("setup.provisioning"));

  /** The one POST. Sets the binding face first, posts the wizardState at the
   *  boundary, and on success renders the response's facts and runs the
   *  locale seam. A 409 routes to the landing; any other refusal names its
   *  cause and offers the retry. */
  const bind = useCallback(async () => {
    setPhase("binding");
    setCause(null);
    const archive = findDemo(state.demo);
    try {
      const { data, response } = await client.POST("/api/setup", {
        body: {
          novel_title: archive !== null ? archive.title : state.title.trim(),
          demo: archive !== null ? archive.slug : undefined,
          genre:
            archive !== null
              ? undefined
              : state.genrePills.length > 0
                ? joinGenres(state.genrePills)
                : undefined,
          target_words: state.targetWords,
          author_typology: state.typology ?? undefined,
          dramatic_form: state.form ?? undefined,
          ai_role: state.aiRole ?? undefined,
          canon_strictness: state.canon ?? undefined,
        },
      });
      if (response.status === 409) {
        // The instance is already complete: the landing, never a re-post.
        // Invalidate the status (this step still observes it) and the shelf,
        // then let the `/` gate read the fresh answer.
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ["setup", "status"] }),
          queryClient.invalidateQueries({ queryKey: ["novels"] }),
        ]);
        void navigate({ to: "/" });
        return;
      }
      if (!response.ok || !data) {
        setCause({ kind: "status", status: response.status });
        setPhase("failed");
        return;
      }
      setResult(data);
      setPhase("bound");
      void queryClient.invalidateQueries({ queryKey: ["setup", "status"] });
      void queryClient.invalidateQueries({ queryKey: ["novels"] });
      // The locale seam: the row exists now, so carry the pre-setup mirror
      // into it. A refusal keeps the mirror; a seam failure never flips the
      // bound phase — the book is bound either way.
      const mirrored = readPreSetupLocale();
      if (mirrored !== null) {
        try {
          const patch = await client.PATCH("/api/settings", { body: { locale: mirrored } });
          if (patch.response.ok) {
            storePreSetupLocale(null);
            void queryClient.invalidateQueries({ queryKey: ["settings"] });
          }
        } catch {
          // The carry-over is a courtesy, not the binding: keep the mirror.
        }
      }
    } catch {
      setCause({ kind: "network" });
      setPhase("failed");
    }
  }, [state, navigate]);

  // Post once on arrival. An empty deep link has no basis to bind, so it
  // falls back to step one with the search intact — never a POST. The ref
  // guard keeps StrictMode's double effect to a single POST.
  //
  // Binding automatically on arrival is BY DRAFT, and accepted by design:
  // in the local-first single-user model the URL is the user's own state —
  // the wizard itself writes it — so a crafted link holds no power the
  // wizard's own URLs don't. The 409 path guards repeats, and db-reset is
  // the local escape hatch.
  useEffect(() => {
    if (!basisComplete(state)) {
      void navigate({ to: "/setup/basis", search: true, replace: true });
      return;
    }
    if (postedRef.current) return;
    postedRef.current = true;
    void bind();
  }, [state, navigate, bind]);

  if (!basisComplete(state)) return null;

  const archive = findDemo(state.demo);
  const facts = phase === "bound" ? result : null;
  // The book object and the hero title read the demo's localized display title
  // on the demo path (the POST still sends archive.title); otherwise the
  // response's facts once bound, else the trimmed blank-path title and first
  // genre pill — an untitled blank answers with the cover's own
  // „Unbenanntes Manuskript".
  const displayTitle =
    archive !== null
      ? demoDisplayTitle(archive, locale)
      : facts !== null
        ? facts.novel_title
        : state.title.trim() !== ""
          ? state.title.trim()
          : t("setup.basis.coverUntitled");
  const displayGenre =
    facts !== null ? facts.genre : archive !== null ? archive.genre : (state.genrePills[0] ?? null);

  // The bound checklist's meta slots: the effective genre and the localized
  // form label on item one, the role label on item three. An absent answer
  // is a dash, never an invented label.
  const form = formLabel(facts?.dramatic_form ?? null);
  const role = roleLabel(facts?.ai_role ?? null);
  const item1Meta = [facts?.genre, form !== null ? t(form) : null].filter(Boolean).join(" • ") || "—";
  const item3Meta = role !== null ? t(role) : "—";

  const disabledButton =
    "inline-flex cursor-not-allowed items-center justify-center gap-2 rounded-lg px-4 py-2 text-label font-medium opacity-50";

  return (
    // The draft's body: full-bleed, pinned ends, the selection pair in tokens.
    // The shell owns the one <main> landmark; this is its content.
    <div className="flex min-h-screen w-full flex-col justify-between selection:bg-secondary-container selection:text-secondary-container-foreground">
      {/* 1. Header & stepper — the wizard's shared chrome, step four active;
          the lock rides the same phase that disables the CTAs below */}
      <WizardHeader activeStep={4} locked={phase === "binding"} />

      {/* 2. The book stage: context pill, cover + meta column, the actions */}
      <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col items-center justify-center px-6 py-8">
        {/* Context & template hint */}
        <div className="mb-5 flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-outline-variant/60 bg-surface-container-highest px-3 py-1 text-eyebrow tracking-wide text-foreground">
            <Icon name="autoStories" size={14} />
            {archive !== null
              ? t("setup.provisioning.contextDemo", {
                  genre: archive.genre,
                  title: demoDisplayTitle(archive, locale),
                })
              : t("setup.provisioning.contextBlank")}
          </span>
        </div>

        {/* The central book stage */}
        <section className="mb-6 w-full rounded-xl border border-border bg-surface-container-lowest p-8 shadow-sm md:p-10">
          <div className="grid grid-cols-1 items-center gap-8 md:grid-cols-12">
            {/* The book object — the shared cover system at hero size */}
            <div className="flex justify-center md:col-span-4">
              <BookCover title={displayTitle} genre={displayGenre} size="hero" />
            </div>

            {/* Title, prose and the phase's own face */}
            <div className="space-y-3 md:col-span-8">
              {phase === "failed" ? (
                // Panel 4: the honest failure card. The POST is atomic, so
                // there is no stopped checklist with false check marks — the
                // card names the failure, keeps the inputs, and offers the
                // retry and the way back.
                <div
                  role="alert"
                  className="rounded-lg border border-border border-l-2 border-l-danger bg-surface-container-lowest p-4 shadow-sm"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-danger">
                      <Icon name="warning" size={18} />
                    </span>
                    <h1 className={`${SERIF} text-title font-bold leading-tight text-foreground`}>
                      {t("setup.provisioning.failedTitle")}
                    </h1>
                  </div>
                  <p className={`${SERIF} mt-1.5 text-body leading-relaxed text-muted`}>
                    {t("setup.provisioning.failedBody")}
                  </p>
                  <p className="mt-2 border-t border-rule pt-2 font-mono text-meta leading-tight text-muted">
                    {cause?.kind === "status"
                      ? t("setup.provisioning.cause.status", { status: cause.status })
                      : t("setup.provisioning.cause.network")}
                  </p>
                </div>
              ) : (
                <>
                  {/* The status line: bound is ready, binding is underway */}
                  {phase === "bound" ? (
                    <div className="flex items-center gap-2">
                      <span aria-hidden="true" className="inline-block h-2 w-2 rounded-full bg-success" />
                      <span className="text-label font-medium text-success">
                        {t("setup.provisioning.readyStatus")}
                      </span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <span aria-hidden="true" className="inline-block h-2 w-2 animate-pulse rounded-full bg-primary" />
                      <span className="text-eyebrow font-semibold uppercase tracking-widest text-primary">
                        {t("setup.provisioning.loading.eyebrow")}
                      </span>
                    </div>
                  )}
                  <h1
                    className={`${SERIF} text-2xl font-normal tracking-tight text-primary md:text-[30px] md:leading-[38px]`}
                  >
                    {phase === "bound"
                      ? t("setup.provisioning.heroTitleBound", { title: displayTitle })
                      : t("setup.provisioning.heroTitleBinding")}
                  </h1>
                  <p className={`${SERIF} max-w-xl text-lg leading-relaxed text-muted`}>
                    {t("setup.provisioning.heroBody")}
                  </p>

                  {phase === "bound" ? (
                    // The bound checklist — exactly the SetupResult's facts.
                    <div className="space-y-2 pt-3">
                      <CheckRow
                        icon={<Icon name="checkCircle" size={18} />}
                        title={t("setup.provisioning.bound.item1")}
                        meta={item1Meta}
                      />
                      <CheckRow
                        icon={<Icon name="checkCircle" size={18} />}
                        title={
                          archive !== null
                            ? t("setup.provisioning.bound.item2")
                            : t("setup.provisioning.bound.item2Blank")
                        }
                        meta={t("setup.provisioning.bound.item2Status", { count: facts?.chapters ?? 0 })}
                      />
                      <CheckRow
                        icon={<Icon name="checkCircle" size={18} />}
                        title={t("setup.provisioning.bound.item3")}
                        meta={item3Meta}
                      />
                      <CheckRow
                        icon={<Icon name="checkCircle" size={18} />}
                        title={t("setup.provisioning.bound.item4")}
                        meta={t("setup.provisioning.bound.typography")}
                      />
                      {/* The completion bar — full, the draft's own label */}
                      <div className="pt-3">
                        <div className="mb-1.5 flex items-center justify-between text-meta">
                          <span className="font-medium text-muted">
                            {t("setup.provisioning.bound.complete")}
                          </span>
                          <span className="flex items-center gap-1 font-semibold text-success">
                            <Icon name="check" size={14} />
                            {t("setup.provisioning.bound.ready")}
                          </span>
                        </div>
                        <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-container-high">
                          <div className="h-full w-full rounded-full bg-success" />
                        </div>
                      </div>
                    </div>
                  ) : (
                    // Panel 3: the binding checklist — two done, the third
                    // spinning, the last two waiting. No percentage anywhere.
                    <div className="space-y-2 pt-3">
                      <CheckRow
                        icon={<Icon name="checkCircle" size={18} />}
                        title={t("setup.provisioning.loading.item1")}
                        meta={t("setup.provisioning.loading.ready")}
                      />
                      <CheckRow
                        icon={<Icon name="checkCircle" size={18} />}
                        title={t("setup.provisioning.loading.item2")}
                        meta={
                          archive !== null
                            ? t("setup.basis.demoChapters", { count: archive.chapters })
                            : "—"
                        }
                      />
                      <div className="flex items-start gap-3 rounded-lg border border-primary/40 bg-primary/5 p-2.5">
                        <span
                          aria-hidden="true"
                          className="mt-0.5 h-3.5 w-3.5 shrink-0 animate-spin rounded-full border border-primary border-t-transparent"
                        />
                        <div className="flex flex-1 flex-col justify-between gap-1 text-left sm:flex-row sm:items-center">
                          <span className="text-body font-medium text-primary">
                            {t("setup.provisioning.loading.item3")}
                          </span>
                          <span className={`${SERIF} animate-pulse text-meta italic text-primary`}>
                            {t("setup.provisioning.loading.item3Status")}
                          </span>
                        </div>
                      </div>
                      <PendingRow n={4} title={t("setup.provisioning.loading.item4")} pending={t("setup.provisioning.loading.pending")} />
                      <PendingRow n={5} title={t("setup.provisioning.loading.item5")} pending={t("setup.provisioning.loading.pending")} />
                      {/* Honest progress: a moving bar, no percentage */}
                      <div className="pt-3">
                        <div className="mb-1.5 flex items-center justify-between text-meta">
                          <span className={`${SERIF} italic text-muted`}>
                            {t("setup.provisioning.loading.sync")}
                          </span>
                        </div>
                        <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-container-high">
                          <div className="h-full w-1/2 animate-pulse rounded-full bg-primary" />
                        </div>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </section>

        {/* 3. The actions, per phase */}
        {phase === "failed" ? (
          <div className="flex w-full flex-col items-center justify-between gap-4 pt-2 sm:flex-row">
            <Link
              to="/setup/basis"
              search={true}
              className={`inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-label font-medium text-muted transition-colors hover:bg-surface-container hover:text-foreground ${FOCUS}`}
            >
              <span className="rotate-180">
                <Icon name="arrowRight" size={16} />
              </span>
              <span>{t("setup.provisioning.backToBasis")}</span>
            </Link>
            <button
              type="button"
              onClick={() => void bind()}
              className={`inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-label font-semibold text-primary-foreground shadow-sm transition-all hover:opacity-95 sm:w-auto ${FOCUS}`}
            >
              <Icon name="refresh" size={18} />
              <span>{t("setup.provisioning.retry")}</span>
            </button>
          </div>
        ) : phase === "bound" ? (
          <div className="w-full pt-2">
            <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
              <Link
                to="/"
                className={`inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-label font-medium text-muted transition-colors hover:bg-surface-container hover:text-foreground ${FOCUS}`}
              >
                <span className="rotate-180">
                  <Icon name="arrowRight" size={16} />
                </span>
                <span>{t("setup.provisioning.cta.back")}</span>
              </Link>
              <div className="flex w-full flex-col items-center gap-3 sm:w-auto sm:flex-row">
                <button
                  type="button"
                  disabled
                  aria-describedby={noteId}
                  className={`${disabledButton} w-full border border-border bg-surface-container-lowest text-foreground sm:w-auto`}
                >
                  <span className="text-secondary">
                    <Icon name="hub" size={17} />
                  </span>
                  <span>{t("setup.provisioning.cta.lore")}</span>
                </button>
                <button
                  type="button"
                  disabled
                  aria-describedby={noteId}
                  className={`${disabledButton} w-full bg-primary text-primary-foreground sm:w-auto`}
                >
                  <span>{t("setup.provisioning.cta.workspace")}</span>
                  <Icon name="arrowRight" size={18} />
                </button>
              </div>
            </div>
            <p id={noteId} className="mt-2 text-center text-meta text-muted">
              {t("setup.welcome.comingSoon")}
            </p>
          </div>
        ) : (
          // Binding: both CTAs wait, no way back mid-bind.
          <div className="flex w-full flex-col items-center justify-end gap-3 pt-2 sm:flex-row">
            <button
              type="button"
              disabled
              className={`${disabledButton} w-full border border-border bg-surface-container-lowest text-foreground sm:w-auto`}
            >
              <span className="text-secondary">
                <Icon name="hub" size={17} />
              </span>
              <span>{t("setup.provisioning.cta.lore")}</span>
            </button>
            <button
              type="button"
              disabled
              className={`${disabledButton} w-full bg-primary text-primary-foreground sm:w-auto`}
            >
              <Icon name="clock" size={18} />
              <span>{t("setup.provisioning.cta.workspace")}</span>
            </button>
          </div>
        )}
      </div>

      {/* 4. The grounded footer */}
      <footer className="w-full border-t border-border bg-surface py-4">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-center gap-2 px-6 text-center text-meta text-muted sm:flex-row">
          <span className="text-outline">
            <Icon name="lock" size={15} />
          </span>
          <span>{t("setup.provisioning.footer.engine")}</span>
        </div>
      </footer>
    </div>
  );
}

/** One done row of the checklist: the success check, the title, and the
 *  meta slot on the right (the draft's two-column row). */
function CheckRow({ icon, title, meta }: { icon: ReactNode; title: string; meta: string }) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-outline-variant/40 bg-surface-container-low p-2.5">
      <span className="mt-0.5 shrink-0 text-success">{icon}</span>
      <div className="flex flex-1 flex-col justify-between gap-1 text-left sm:flex-row sm:items-center">
        <span className="text-body font-medium text-foreground">{title}</span>
        <span className="text-meta text-muted">{meta}</span>
      </div>
    </div>
  );
}

/** One waiting row of the binding checklist: the numbered ring, the muted
 *  title, and the mono „ausstehend" (panel 3's planned items). */
function PendingRow({ n, title, pending }: { n: number; title: string; pending: string }) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-outline-variant/30 bg-surface-container-low/50 p-2.5">
      <span className="mt-0.5 flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full border border-outline-variant font-mono text-[8px] text-muted">
        {n}
      </span>
      <div className="flex flex-1 flex-col justify-between gap-1 text-left sm:flex-row sm:items-center">
        <span className="text-body font-medium text-muted">{title}</span>
        <span className="font-mono text-meta text-muted">{pending}</span>
      </div>
    </div>
  );
}
