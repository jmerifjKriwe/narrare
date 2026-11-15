/**
 * The new-book dialog — the owner-picked `new-book-dialog` draft ported
 * onto the shell's tokens: a modal over the scrimmed shelf (the token's
 * own 40% scrim pair), three fields and a live cover, nothing more.
 *
 * The form is the wizard step 1's seam shapes re-owned on this side of the
 * capability boundary (newBook.ts): the title feeds the shared BookCover
 * at `wizard` size as it is typed, the five genre pills join to the one
 * ≤80-char string the backend binds (a pill whose addition would overflow
 * is disabled with the honest note), and the word target keeps the draft's
 * slider, default and format-category display. The inheritance note stands
 * verbatim — the dialog's answers never write wizard settings; dramaturgy,
 * AI role and canon stay the atelier's until the workspace exists.
 *
 * `Anlegen` posts the three answers once (busy CTA, the dialog held against
 * every close path while the ask runs); success closes and the shelf's own
 * refetch carries the new book — the newest `updated_at` leads as the hero,
 * the honest outcome of the column, never a hand-patched insert. A refusal
 * keeps every answer and offers the family's error line: the loss-free
 * message, the real status, and „Erneut versuchen" re-running the same ask.
 *
 * Semantics at modal weight, the Task 7/8 popover discipline grown up:
 * `role="dialog"` + `aria-modal`, labelled by its own heading, focus lands
 * on the title field, Tab wraps inside the panel, Escape/scrim/Abbrechen/
 * the cross close and hand focus back to the opener (the page owns that
 * return — the opener may be the empty panel the create itself retires).
 * The state is component state: unmounted is gone, the draft carries no
 * draft-persistence.
 *
 * Deviations kept honest (the report lists them): the draft's hand-drawn
 * book is the shared BookCover, so the „Narrare Press" line stands under
 * the book object instead of on its foot; the footer's two system-status
 * claims and the „Atelier-Kanon: Stufe Alpha" tag are omitted — no row
 * backs them for a book that does not exist yet; the slider's 20k–140k
 * range is the draft's own, the column's full bounds stay the wizard's.
 *
 * Token mapping (the draft's hexes → the shell's roles): the scrim →
 * bg-scrim (the overlay pair's 40%), dialog-shadow → shadow-overlay,
 * surface-bright/surface → surface, #E6DBCD hairlines → rule,
 * primary-container → primary (the light half is the draft's #743B1F
 * exactly), amber-focus → focus, text-muted-light → muted,
 * surface-container-low → surface-container-low, state-danger → danger.
 * Icon faces (spec §6.9): close → cross, sync → historyEdu (the wizard's
 * own face for the live-title note), book_2 → menuBook, arrow_forward →
 * arrowRight; progress_activity is the shell's border spinner.
 */

import { useEffect, useId, useRef, useState } from "react";

import { BookCover } from "@shell/lib/cover/BookCover";
import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import { useCreateNovel } from "@shell/lib/query";
import { formatWordCount } from "@shell/lib/words";
import { Icon } from "@shell/ui/icons";

import {
  DEFAULT_TARGET_WORDS,
  GENRE_CAP,
  GENRE_PILL_DEFS,
  WORDS_PER_NORMSEITE,
  joinGenres,
  wordBand,
  wouldOverflow,
  type Band,
} from "./newBook";

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The shell's focus ring on every control the dialog offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The trap's population: every live control inside the panel, in DOM
 *  order — the disabled CTA and the busy-held buttons stay out of it. */
const FOCUSABLE =
  'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])';

/** The draft's slider: its own range and step, the default inside it. */
const WORDS_MIN = 20_000;
const WORDS_MAX = 140_000;
const WORDS_STEP = 5_000;

/** The gauge's format categories — the wizard step 1's bands and ranges,
 *  re-keyed into this catalog so the dialog speaks its own words. */
const BANDS: Record<Band, { band: MessageKey; range: MessageKey }> = {
  short: { band: "writing.shelf.dialog.band.short", range: "writing.shelf.dialog.range.short" },
  novella: { band: "writing.shelf.dialog.band.novella", range: "writing.shelf.dialog.range.novella" },
  novel: { band: "writing.shelf.dialog.band.novel", range: "writing.shelf.dialog.range.novel" },
  epic: { band: "writing.shelf.dialog.band.epic", range: "writing.shelf.dialog.range.epic" },
};

/** The slider's three scale marks, the draft's own labels; the active
 *  band's mark wears the primary ink (the short band sits below the
 *  slider's floor and never lights). */
const SCALES: readonly { band: Band; key: MessageKey }[] = [
  { band: "novella", key: "writing.shelf.dialog.scale.novella" },
  { band: "novel", key: "writing.shelf.dialog.scale.novel" },
  { band: "epic", key: "writing.shelf.dialog.scale.epic" },
];

/** The shell's busy face (the quick menu's spinner), on the primary CTA:
 *  a ring with one transparent quarter, turning. No glyph — the motion is
 *  the mark. */
function Spinner() {
  return (
    <span
      aria-hidden="true"
      className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border border-primary-foreground border-t-transparent"
    />
  );
}

export function NewBookDialog({ onClose }: { onClose: (created: boolean) => void }) {
  const t = useTranslation();
  // The three answers, transient by design: an unmounted dialog is a
  // forgotten one — the draft carries no draft-persistence.
  const [title, setTitle] = useState("");
  const [pills, setPills] = useState<readonly string[]>([]);
  const [words, setWords] = useState(DEFAULT_TARGET_WORDS);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const titleRef = useRef<HTMLInputElement | null>(null);
  const headingId = useId();
  const titleInputId = useId();
  const titleErrorId = useId();
  const genreLabelId = useId();
  const wordsId = useId();
  const formId = useId();
  const create = useCreateNovel();

  const complete = title.trim() !== "";
  const activeBand = wordBand(words);
  const capBlocked = GENRE_PILL_DEFS.some(
    (pill) => !pills.includes(pill.value) && wouldOverflow(pills, pill.value),
  );

  // Opening lands focus on the title field (the wizard's own first move)
  // and holds the page behind the scrim still; both leave with the dialog.
  useEffect(() => {
    titleRef.current?.focus();
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, []);

  // Escape closes — never mid-flight — and Tab wraps inside the panel at
  // both ends, the modal weight of the popover's keyboard discipline.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        if (busy) return;
        event.preventDefault();
        onClose(false);
        return;
      }
      if (event.key !== "Tab") return;
      const panel = panelRef.current;
      if (panel === null) return;
      const nodes = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (nodes.length === 0) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      const active = document.activeElement;
      if (event.shiftKey) {
        if (active === first || !panel.contains(active)) {
          event.preventDefault();
          last.focus();
        }
      } else if (active === last || !panel.contains(active)) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  function togglePill(value: string) {
    setPills((previous) =>
      previous.includes(value) ? previous.filter((pill) => pill !== value) : [...previous, value],
    );
  }

  /** The one POST: the trimmed title, the joined pills (absent when none),
   *  and the target — three keys, never a wizard setting. Success closes
   *  and the hook's `["novels"]` invalidation refetches the shelf; a
   *  refusal keeps the answers and names itself on the family's line. */
  function submit() {
    if (!complete || busy) return;
    setBusy(true);
    setError(null);
    create.mutate(
      {
        title: title.trim(),
        genre: pills.length > 0 ? joinGenres(pills) : undefined,
        target_words: words,
      },
      {
        onSuccess: () => {
          setBusy(false);
          onClose(true);
        },
        onError: (failure) => {
          setBusy(false);
          setError(failure.message);
        },
      },
    );
  }

  return (
    // The scrim: the token's own 40% pair over the shelf, the draft's soft
    // blur. A press on the scrim itself closes; a press inside does not.
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-scrim p-4 backdrop-blur-[4px]"
      onClick={(event) => {
        if (!busy && event.target === event.currentTarget) onClose(false);
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={headingId}
        className="flex max-h-[calc(100vh-2rem)] w-full max-w-[860px] flex-col rounded-lg border border-border bg-surface shadow-overlay"
      >
        {/* The bookbinder's accent strip, the draft's own gradient. */}
        <div aria-hidden="true" className="h-1 shrink-0 bg-gradient-to-r from-primary via-focus to-primary" />

        <header className="flex shrink-0 items-start justify-between gap-4 border-b border-rule px-6 pb-4 pt-5 md:px-8">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-eyebrow font-semibold uppercase tracking-wider text-focus">
                {t("writing.shelf.dialog.eyebrow")}
              </span>
              <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-focus/60" />
              <span className="text-meta text-muted">{t("writing.shelf.dialog.mode")}</span>
            </div>
            <h2
              id={headingId}
              className={`${SERIF} mt-1 text-3xl font-semibold leading-tight tracking-tight text-primary`}
            >
              {t("writing.shelf.dialog.title")}
            </h2>
            <p className="mt-1 text-body text-muted">{t("writing.shelf.dialog.subtitle")}</p>
          </div>
          <button
            type="button"
            aria-label={t("writing.shelf.dialog.close")}
            disabled={busy}
            onClick={() => onClose(false)}
            className={`flex h-8 w-8 shrink-0 items-center justify-center rounded border border-border text-muted transition-colors hover:bg-surface-container hover:text-foreground ${FOCUS} ${busy ? "cursor-not-allowed opacity-50" : ""}`}
          >
            <Icon name="cross" size={16} />
          </button>
        </header>

        {/* The body is the scroll region on short viewports; header and
            footer stay pinned, so the actions never fall below the fold.
            Its scrollbar speaks the token palette, not the browser's. */}
        <div className="overflow-y-auto [scrollbar-color:var(--color-outline-variant)_transparent] [scrollbar-width:thin] [&::-webkit-scrollbar-thumb:hover]:bg-outline [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-outline-variant [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar]:w-2">
          <div className="grid grid-cols-1 gap-8 px-6 py-6 md:grid-cols-12 md:px-8 md:py-7">
            {/* The form: exactly three fields, the draft's own order. */}
            <form
              id={formId}
              className="flex flex-col gap-6 md:col-span-7"
              onSubmit={(event) => {
                event.preventDefault();
                submit();
              }}
            >
              {/* 1. Arbeitstitel — required, live on the cover. */}
              <div className="flex flex-col gap-1.5">
                <div className="flex items-baseline justify-between gap-2">
                  <label htmlFor={titleInputId} className="text-label font-semibold text-foreground">
                    {t("writing.shelf.dialog.titleLabel")}
                    <span aria-hidden="true" className="text-danger">
                      {" *"}
                    </span>
                  </label>
                  <span className="text-eyebrow uppercase text-muted">
                    {t("writing.shelf.dialog.titleRequired")}
                  </span>
                </div>
                <div className="relative">
                  <input
                    id={titleInputId}
                    ref={titleRef}
                    type="text"
                    maxLength={200}
                    required
                    aria-invalid={!complete}
                    aria-describedby={!complete ? titleErrorId : undefined}
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    placeholder={t("writing.shelf.dialog.titlePlaceholder")}
                    className={`h-10 w-full rounded border bg-surface-container-lowest px-3 text-body text-foreground outline-none transition-shadow focus:border-focus focus:ring-1 focus:ring-focus ${
                      complete ? "border-border" : "border-danger pr-9"
                    }`}
                  />
                  {!complete && (
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-danger">
                      <Icon name="cross" size={14} />
                    </span>
                  )}
                </div>
                <p className="flex items-center gap-1.5 text-meta text-muted">
                  <span className="text-focus">
                    <Icon name="historyEdu" size={14} />
                  </span>
                  {t("writing.shelf.dialog.titleSync")}
                </p>
                {!complete && (
                  <p
                    id={titleErrorId}
                    className={`${SERIF} flex items-start gap-1 text-meta italic leading-tight text-danger`}
                  >
                    {t("writing.shelf.dialog.titleError")}
                  </p>
                )}
              </div>
  
              {/* 2. Genre — the five pills, multi-select, joined under the cap. */}
              <div className="flex flex-col gap-2">
                <div className="flex items-center justify-between gap-2">
                  <span id={genreLabelId} className="text-label font-semibold text-foreground">
                    {t("writing.shelf.dialog.genreLabel")}
                  </span>
                  <span className="text-meta text-muted">{t("writing.shelf.dialog.genreHint")}</span>
                </div>
                <div role="group" aria-labelledby={genreLabelId} className="flex flex-wrap gap-2 pt-0.5">
                  {GENRE_PILL_DEFS.map((pill) => {
                    const selected = pills.includes(pill.value);
                    const blocked = !selected && wouldOverflow(pills, pill.value);
                    return (
                      <button
                        key={pill.value}
                        type="button"
                        aria-pressed={selected}
                        disabled={blocked}
                        onClick={() => togglePill(pill.value)}
                        className={
                          selected
                            ? `flex items-center gap-1.5 rounded border border-primary bg-primary px-3 py-1.5 text-label font-medium text-primary-foreground shadow-sm ${FOCUS}`
                            : blocked
                              ? "cursor-not-allowed rounded border border-border bg-surface-container-lowest px-3 py-1.5 text-label text-muted opacity-50"
                              : `rounded border border-border bg-surface-container-lowest px-3 py-1.5 text-label text-foreground hover:bg-surface-container ${FOCUS}`
                        }
                      >
                        {selected && <Icon name="check" size={14} />}
                        {t(pill.key)}
                      </button>
                    );
                  })}
                </div>
                {capBlocked && (
                  <p className="text-meta text-muted">
                    {t("writing.shelf.dialog.genreCapNote", { cap: GENRE_CAP })}
                  </p>
                )}
              </div>
  
              {/* 3. Ziel-Umfang — the draft's slider, value chip and category. */}
              <div className="flex flex-col gap-2 rounded border border-rule bg-surface-container-low p-3.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <label htmlFor={wordsId} className="text-label font-semibold text-foreground">
                    {t("writing.shelf.dialog.wordsLabel")}
                  </label>
                  <span className="flex items-center gap-1 rounded border border-border bg-surface-container-lowest px-2.5 py-1">
                    <span className="font-mono text-label font-bold tabular-nums text-primary">
                      {formatWordCount(words)}
                    </span>
                    <span className="text-eyebrow uppercase text-muted">
                      {t("writing.shelf.dialog.wordsUnit")}
                    </span>
                  </span>
                </div>
                <div className="py-1">
                  <input
                    id={wordsId}
                    type="range"
                    min={WORDS_MIN}
                    max={WORDS_MAX}
                    step={WORDS_STEP}
                    value={words}
                    aria-valuetext={`${formatWordCount(words)} ${t("writing.shelf.dialog.wordsUnit")}`}
                    onChange={(event) => setWords(Number(event.target.value))}
                    className={`w-full cursor-pointer accent-primary ${FOCUS}`}
                  />
                  <div className="mt-1 flex justify-between gap-2 font-mono text-[10px] text-muted">
                    {SCALES.map((scale) => (
                      <span
                        key={scale.band}
                        className={scale.band === activeBand ? "font-semibold text-primary" : ""}
                      >
                        {t(scale.key)}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="flex flex-col justify-between gap-1 border-t border-rule pt-2 sm:flex-row sm:items-center">
                  <span className="flex flex-wrap items-baseline gap-1.5">
                    <span className="text-eyebrow font-bold uppercase text-focus">
                      {t(BANDS[activeBand].band)}
                    </span>
                    <span className="text-meta text-muted">({t(BANDS[activeBand].range)})</span>
                  </span>
                  <span className="text-meta text-muted">
                    {t("writing.shelf.dialog.normseiten", {
                      count: Math.floor(words / WORDS_PER_NORMSEITE),
                    })}
                  </span>
                </div>
              </div>
  
              {/* The inheritance note, verbatim — the atelier keeps its settings. */}
              <div className="flex items-start gap-2.5 rounded border border-rule bg-surface-container/60 p-3 text-muted">
                <span className="mt-0.5 shrink-0 text-focus">
                  <Icon name="menuBook" size={18} />
                </span>
                <p className="text-meta leading-relaxed">{t("writing.shelf.dialog.inheritance")}</p>
              </div>
            </form>
  
            {/* The live cover — the shared book object at wizard size. */}
            <div className="flex flex-col items-center justify-between gap-3 md:col-span-5 md:border-l md:border-rule md:pl-4">
              <div className="flex w-full flex-col items-center">
                <span className="mb-3 text-eyebrow uppercase tracking-widest text-muted">
                  {t("writing.shelf.dialog.coverEyebrow")}
                </span>
                <BookCover
                  title={title.trim() || t("writing.shelf.dialog.coverUntitled")}
                  genre={pills[0] ?? null}
                  size="wizard"
                  className="transition-transform hover:scale-[1.01]"
                />
                {/* The press line: the cover system is frozen, so the draft's
                    publisher foot stands under the book object, not on it. */}
                <span className="mt-3 text-eyebrow uppercase tracking-widest text-muted">
                  {t("writing.shelf.dialog.press", { year: new Date().getFullYear() })}
                </span>
                <p className="mt-2 text-center text-meta text-muted">
                  {t("writing.shelf.dialog.coverCaption")}
                </p>
              </div>
            </div>
          </div>
  
          {/* The family's error line: loss-free message, the real refusal,
              and the retry that re-runs the very ask. The answers stand. */}
          {error !== null && (
            <div
              role="alert"
              className="mx-6 mb-4 rounded-lg border border-rule border-l-2 border-l-danger bg-surface-container-lowest p-3 md:mx-8"
            >
              <div className="flex items-start gap-2">
                <span className="mt-0.5 shrink-0 text-danger">
                  <Icon name="warning" size={16} />
                </span>
                <div className="flex-1">
                  <p className="text-meta leading-tight text-foreground">
                    {t("writing.shelf.dialog.error")}
                  </p>
                  <p className="mt-0.5 font-mono text-meta text-danger">{error}</p>
                  <button
                    type="button"
                    onClick={submit}
                    className={`mt-1 inline-flex items-center gap-1 text-meta font-medium text-primary underline underline-offset-2 transition-colors hover:text-foreground ${FOCUS}`}
                  >
                    {t("writing.shelf.error.retry")}
                    <Icon name="refresh" size={12} />
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        <footer className="flex shrink-0 items-center justify-end gap-3 border-t border-rule px-6 py-4 md:px-8">
          <button
            type="button"
            disabled={busy}
            onClick={() => onClose(false)}
            className={`rounded border border-transparent px-4 py-2 text-label text-muted transition-colors hover:border-border hover:bg-surface-container hover:text-foreground ${FOCUS} ${busy ? "cursor-not-allowed opacity-50" : ""}`}
          >
            {t("writing.shelf.dialog.cancel")}
          </button>
          {/* The state flip (disabled ↔ ready) switches colour instantly:
              only hover opacity and shadow animate. A colour transition
              here would spend 150 ms in a blend that clears no AA bar —
              the contrast gate measures the face mid-flight. */}
          <button
            type="submit"
            form={formId}
            disabled={!complete || busy}
            className={`flex items-center gap-2 rounded px-5 py-2.5 text-label font-semibold shadow-sm transition-[opacity,box-shadow] ${FOCUS} ${
              complete && !busy
                ? "cursor-pointer bg-primary text-primary-foreground hover:opacity-95 hover:shadow-md"
                : "cursor-not-allowed bg-surface-container-high text-muted shadow-none"
            }`}
          >
            {busy ? <Spinner /> : <Icon name="plus" size={16} />}
            <span>{busy ? t("writing.shelf.dialog.busy") : t("writing.shelf.dialog.create")}</span>
            {!busy && <Icon name="arrowRight" size={16} />}
          </button>
        </footer>
      </div>
    </div>
  );
}
