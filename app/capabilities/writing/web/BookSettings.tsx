/**
 * The book-settings dialog (W4 Task 19) — the round's dedicated
 * `workspace-book-settings` draft ported onto the shell's tokens: the
 * modal over the scrimmed workspace, five sections (book & metadata,
 * status & target, the KI partner family, the series context, the
 * atelier), the pinned header (the book's own chip) and footer (the
 * inheritance note — now TRUE: this surface edits what setup bound —
 * beside Abbrechen and Speichern).
 *
 * The fields read the REAL rows: the novel (metadata, status, target,
 * the four wizard answers, the series link), the settings row (the
 * atelier's author name and daily goal) and the user's series list.
 * Speichern carries the DIFF alone — the novel PATCH's `model_fields_set`
 * contract mirrored field by field, a carried null the honest clear —
 * and the atelier's changes ride the settings PATCH (the locale always
 * carried, the schema's own rule). A pristine save closes without a wire
 * ask. The series create lands inline (the row exists once the POST
 * lands; the link rides the save).
 *
 * The dirty-state rule is the tree dialogs' own (the whole-branch
 * review's ruling): any typed change holds the scrim/Escape and the
 * Fertig cross; only Abbrechen and Speichern answer while edits stand.
 * The keyboard discipline rides the shell's one home (@shell/ui/
 * modalKeys, #895). Focus lands on the title field; every close returns
 * it to the opener (the identity card's door).
 *
 * Honest readings of the draft (the report lists them): the genre pills
 * are the canonical five the new-book dialog binds (the draft's mock
 * names are draft data; a free-text genre part rides the remainder, never
 * silently dropped); the volume is the integer the column stores (the
 * draft's „I" is a mock face — the shelf speaks the number); the dramatic
 * form select is the wizard's five-form vocabulary (the draft overlooks
 * the fourth wizard field — the established pattern applies); the series
 * note keeps the standalone sentence and drops the lore-sharing claim no
 * row backs yet; the canon badge names the three drafted stops (1/3/5),
 * the between-stops carry the number alone. The target input opens on
 * the locale's grouped figure and answers to the column's full bounds —
 * „beliebig wählbar", the shelf ledger's row 10.
 */

import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";

import type { Novel, NovelChanges, Series } from "@shell/lib/api/client";
import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import { queryClient, useSettingsQuery } from "@shell/lib/query";
import { Icon, type IconName } from "@shell/ui/icons";
import { useModalKeys } from "@shell/ui/modalKeys";
import type { UseQueryResult } from "@tanstack/react-query";

import {
  formatGoalInput,
  genresFromNovel,
  joinGenresWithRest,
  parseVolume,
  parseWordGoal,
  seriesIdForTitle,
} from "./bookSettings";
import { GENRE_PILL_DEFS, GENRE_CAP, wordBand, wouldOverflow, type Band } from "./newBook";
import { progress } from "./shelf";
import { ErrorLine, Spinner } from "./TreeDialogs";
import { useCreateSeries, useSeriesQuery, useUpdateNovel, useUpdateSettings } from "./workspace";

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The shell's focus ring on every control the dialog offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The draft's input face — the card ground, the amber focus border. */
const INPUT =
  "h-9 w-full rounded border border-border bg-surface-container-lowest px-3 text-body text-foreground outline-none transition-shadow focus:border-focus focus:ring-1 focus:ring-focus";

/** The gauge's format categories — the new-book dialog's own keys, so a
 *  target bands identically on both surfaces. */
const BANDS: Record<Band, { band: MessageKey; range: MessageKey }> = {
  short: { band: "writing.shelf.dialog.band.short", range: "writing.shelf.dialog.range.short" },
  novella: { band: "writing.shelf.dialog.band.novella", range: "writing.shelf.dialog.range.novella" },
  novel: { band: "writing.shelf.dialog.band.novel", range: "writing.shelf.dialog.range.novel" },
  epic: { band: "writing.shelf.dialog.band.epic", range: "writing.shelf.dialog.range.epic" },
};

/** The three typologies — the kernel registry's keys, the draft's cards. */
const TYPOLOGIES: readonly { id: string; label: MessageKey; body: MessageKey }[] = [
  { id: "plotter", label: "writing.settings.typologyPlotterLabel", body: "writing.settings.typologyPlotterBody" },
  { id: "pantser", label: "writing.settings.typologyPantserLabel", body: "writing.settings.typologyPantserBody" },
  { id: "plantser", label: "writing.settings.typologyPlantserLabel", body: "writing.settings.typologyPlantserBody" },
];

/** The four AI roles — the kernel registry's keys, the draft's cards. */
const ROLES: readonly { id: string; label: MessageKey; meta: MessageKey }[] = [
  { id: "archivar", label: "writing.settings.roleArchivarLabel", meta: "writing.settings.roleArchivarMeta" },
  { id: "coautor", label: "writing.settings.roleCoautorLabel", meta: "writing.settings.roleCoautorMeta" },
  { id: "lektor", label: "writing.settings.roleLektorLabel", meta: "writing.settings.roleLektorMeta" },
  { id: "sparring", label: "writing.settings.roleSparringLabel", meta: "writing.settings.roleSparringMeta" },
];

/** The five dramatic forms — the wizard registry's vocabulary, re-keyed
 *  into this catalog (rule 1: no cross-capability import; the dialog's
 *  own words, the same ids the backend binds). The draft overlooks the
 *  field; the select is the established pattern's honest extension. */
const FORMS: readonly { id: string; label: MessageKey }[] = [
  { id: "three-act", label: "writing.settings.formThreeAct" },
  { id: "heros-journey", label: "writing.settings.formHerosJourney" },
  { id: "seven-point", label: "writing.settings.formSevenPoint" },
  { id: "five-act", label: "writing.settings.formFiveAct" },
  { id: "save-the-cat", label: "writing.settings.formSaveTheCat" },
];

/** The canon's three named stops — the draft's own labels; the between
 *  stops (2/4) carry the number alone, never an invented name. */
const CANON_NAMES: Record<number, MessageKey> = {
  1: "writing.settings.canonFree",
  3: "writing.settings.canonBalanced",
  5: "writing.settings.canonStrict",
};

/** The manuscript languages the draft's segment draws — the catalog's
 *  own three, the codes the novel's language column stores. */
const LANGUAGES: readonly string[] = ["de", "en", "fr"];

/** The status vocabulary — the shelf pill's own keys. */
const STATUSES: readonly { id: string; label: MessageKey }[] = [
  { id: "draft", label: "writing.shelf.status.draft" },
  { id: "revision", label: "writing.shelf.status.revision" },
  { id: "final", label: "writing.shelf.status.final" },
];

/** The radio groups' keyboard contract, the wizard's: arrows cycle and
 *  wrap, Home/End jump to the ends, Space/Enter select; the move selects
 *  and focuses. */
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

/** One section's head — the draft's icon + title left, eyebrow right. */
function SectionHead({ icon, title, eyebrow }: { icon: IconName; title: string; eyebrow: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <div className="flex items-center gap-2">
        <span className="text-primary">
          <Icon name={icon} size={17} />
        </span>
        <h3 className="text-emph font-semibold text-foreground">{title}</h3>
      </div>
      <span className="text-eyebrow font-semibold uppercase tracking-wider text-muted">{eyebrow}</span>
    </div>
  );
}

/** The segmented radiogroup — language and status, the draft's faces. */
function Segment({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: readonly { id: string; label: string }[];
  value: string | null;
  onChange: (id: string) => void;
}) {
  const labelId = useId();
  const refs = useRef<Partial<Record<string, HTMLElement | null>>>({});
  const order = options.map((option) => option.id);
  return (
    <div>
      <span id={labelId} className="mb-1.5 block text-label font-medium text-foreground">
        {label}
      </span>
      <div
        role="radiogroup"
        aria-labelledby={labelId}
        className="grid w-full grid-cols-3 gap-0.5 rounded border border-border bg-surface-container p-0.5"
      >
        {options.map((option, at) => {
          const selected = value === option.id;
          return (
            <button
              key={option.id}
              type="button"
              role="radio"
              aria-checked={selected}
              tabIndex={selected || (value === null && at === 0) ? 0 : -1}
              ref={(node) => {
                refs.current[option.id] = node;
              }}
              onClick={() => onChange(option.id)}
              onKeyDown={(event) => radioKey(event, order, at, onChange, refs)}
              className={`rounded py-1.5 text-label transition-colors ${FOCUS} ${
                selected
                  ? "bg-primary font-semibold text-primary-foreground shadow-sm"
                  : "text-muted hover:text-foreground"
              }`}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** The loading face — the settings row is the boot's own read (cached),
 *  the series list the dialog's first ask; the panel stands labelled and
 *  busy until both settle, then the form mounts on the real values. */
function LoadingPanel() {
  const t = useTranslation();
  const headingId = useId();
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-scrim p-4 backdrop-blur-[1px]">
      <div
        role="dialog"
        aria-modal="true"
        aria-busy="true"
        aria-labelledby={headingId}
        className="w-full max-w-sm rounded-lg border border-border bg-panel p-6 text-center shadow-overlay"
      >
        <h2 id={headingId} className={`${SERIF} text-body font-semibold text-foreground`}>
          {t("writing.settings.title")}
        </h2>
        <p role="status" className="mt-2 text-meta text-muted">
          {t("writing.settings.loading")}
        </p>
      </div>
    </div>
  );
}

export function BookSettings({
  novel,
  openerId,
  onClose,
}: {
  novel: Novel;
  openerId: string;
  onClose: () => void;
}) {
  const settings = useSettingsQuery();
  const series = useSeriesQuery();
  // The form mounts once the reads settle — its state initializers read
  // the real rows, never a guessed baseline. A series refusal still
  // mounts the form (the section answers honestly with its retry).
  if (!settings.isSuccess || series.isPending) return <LoadingPanel />;
  return (
    <SettingsForm
      novel={novel}
      atelier={settings.data}
      series={series}
      openerId={openerId}
      onClose={onClose}
    />
  );
}

function SettingsForm({
  novel,
  atelier,
  series,
  openerId,
  onClose,
}: {
  novel: Novel;
  atelier: { locale: string | null; author_name: string | null; daily_goal_words: number | null };
  series: UseQueryResult<Series[]>;
  openerId: string;
  onClose: () => void;
}) {
  const t = useTranslation();

  // --- The answers, transient against the stored baseline ---------------
  // The wizard baselines normalize undefined to null — the server's JSON
  // always carries the keys, the client's optional types may not.
  const baseTypology = novel.author_typology ?? null;
  const baseForm = novel.dramatic_form ?? null;
  const baseRole = novel.ai_role ?? null;
  const baseCanon = novel.canon_strictness ?? null;
  const genreSplit = genresFromNovel(novel.genre);
  const [title, setTitle] = useState(novel.title);
  const [author, setAuthor] = useState(novel.author ?? "");
  const [pills, setPills] = useState<readonly string[]>(genreSplit.pills);
  // A free-text genre part no pill names rides verbatim — a save never
  // silently drops what the pills cannot show.
  const genreRest = useRef(genreSplit.rest);
  const [language, setLanguage] = useState<string | null>(novel.language ?? null);
  const [blurb, setBlurb] = useState(novel.blurb ?? "");
  const [status, setStatus] = useState<string | null>(novel.status ?? null);
  const [targetRaw, setTargetRaw] = useState(formatGoalInput(novel.target_words ?? null));
  const [typology, setTypology] = useState<string | null>(baseTypology);
  const [form, setForm] = useState(baseForm ?? "");
  const [role, setRole] = useState<string | null>(baseRole);
  const [canon, setCanon] = useState<number | null>(baseCanon);
  const [seriesId, setSeriesId] = useState<string | null>(
    seriesIdForTitle(series.data ?? [], novel.series_title ?? null),
  );
  // The link's baseline — the select's value at mount (or the adoption
  // below when the list arrives late). The diff compares against it, so
  // a late list never reads as a typed change.
  const seriesBaseline = useRef(seriesId);
  const seriesTouched = useRef(false);
  const [volumeRaw, setVolumeRaw] = useState(novel.series_volume != null ? String(novel.series_volume) : "");
  const [atelierAuthor, setAtelierAuthor] = useState(atelier.author_name ?? "");
  const [dailyRaw, setDailyRaw] = useState(formatGoalInput(atelier.daily_goal_words));

  // The series list may land after the form mounted (a retry after a
  // refusal): adopt the book's link once, until the writer touches the
  // select — then the choice is theirs alone.
  useEffect(() => {
    if (seriesTouched.current || series.data === undefined) return;
    const resolved = seriesIdForTitle(series.data, novel.series_title ?? null);
    seriesBaseline.current = resolved;
    setSeriesId(resolved);
  }, [series.data, novel.series_title]);

  // --- The inline series create -----------------------------------------
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  // The create's refusal face: the duplicate name (409) speaks its own
  // note, every other refusal the family's loss-free line.
  const [createError, setCreateError] = useState<null | "duplicate" | "failed">(null);
  const createSeries = useCreateSeries();

  // --- The save ----------------------------------------------------------
  const updateNovel = useUpdateNovel(novel.id);
  const updateSettings = useUpdateSettings();
  const busy = updateNovel.isPending || updateSettings.isPending || createSeries.isPending;
  const [error, setError] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<{ title?: boolean; target?: boolean; daily?: boolean; volume?: boolean }>({});

  const targetValue = parseWordGoal(targetRaw);
  const dailyValue = parseWordGoal(dailyRaw);
  const volumeValue = parseVolume(volumeRaw);
  const genreValue = joinGenresWithRest(pills, genreRest.current);

  const dirty =
    title !== novel.title ||
    author !== (novel.author ?? "") ||
    genreValue !== novel.genre ||
    language !== novel.language ||
    blurb !== (novel.blurb ?? "") ||
    status !== novel.status ||
    targetValue !== novel.target_words ||
    typology !== baseTypology ||
    (form === "" ? null : form) !== baseForm ||
    role !== baseRole ||
    canon !== baseCanon ||
    seriesId !== seriesBaseline.current ||
    (seriesId !== null && volumeValue !== novel.series_volume) ||
    atelierAuthor !== (atelier.author_name ?? "") ||
    dailyValue !== atelier.daily_goal_words;

  const panelRef = useRef<HTMLDivElement | null>(null);
  const titleRef = useRef<HTMLInputElement | null>(null);
  const headingId = useId();
  const typologyRefs = useRef<Partial<Record<string, HTMLElement | null>>>({});
  const roleRefs = useRef<Partial<Record<string, HTMLElement | null>>>({});

  // Focus lands on the title field; every close returns it to the opener
  // (the identity card's door). The page behind the scrim holds still.
  useEffect(() => {
    titleRef.current?.focus();
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
      document.getElementById(openerId)?.focus();
    };
  }, [openerId]);

  useModalKeys(panelRef, () => {
    if (!busy && !dirty) onClose();
  });

  /** The one save: validate, build the diff, ride the two PATCHes in
   *  order (the novel first, the atelier after), close on success. A
   *  refusal keeps every answer and stands the family's error line —
   *  the retry re-runs this very ask. */
  async function save() {
    const errors: typeof fieldErrors = {};
    if (title.trim() === "") errors.title = true;
    if (targetValue === "invalid") errors.target = true;
    if (dailyValue === "invalid") errors.daily = true;
    if (seriesId !== null && volumeValue === "invalid") errors.volume = true;
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;
    // Past the guard the answers are numbers or the honest unset — the
    // "invalid" face returned above (the type narrowing the guard earns).
    const target = targetValue as number | null;
    const daily = dailyValue as number | null;
    const volume = volumeValue as number | null;

    const changes: NovelChanges = {};
    const trimmedTitle = title.trim();
    if (trimmedTitle !== novel.title) changes.title = trimmedTitle;
    const trimmedAuthor = author.trim() === "" ? null : author.trim();
    if (trimmedAuthor !== novel.author) changes.author = trimmedAuthor;
    if (genreValue !== novel.genre) changes.genre = genreValue;
    if (language !== novel.language) changes.language = language;
    const trimmedBlurb = blurb.trim() === "" ? null : blurb.trim();
    if (trimmedBlurb !== novel.blurb) changes.blurb = trimmedBlurb;
    if (status !== novel.status) changes.status = status;
    if (target !== novel.target_words) changes.target_words = target;
    if (typology !== baseTypology) changes.author_typology = typology;
    const formValue = form === "" ? null : form;
    if (formValue !== baseForm) changes.dramatic_form = formValue;
    if (role !== baseRole) changes.ai_role = role;
    if (canon !== baseCanon) changes.canon_strictness = canon;
    if (seriesId !== seriesBaseline.current) {
      changes.series_id = seriesId;
      // Leaving a series takes the volume with it — the number belongs
      // to the link (the service's own rule, mirrored).
      if (seriesId === null) changes.series_volume = null;
      else if (volume !== novel.series_volume) changes.series_volume = volume;
    } else if (seriesId !== null && volume !== novel.series_volume) {
      changes.series_volume = volume;
    }

    const trimmedAtelierAuthor = atelierAuthor.trim() === "" ? null : atelierAuthor.trim();
    const atelierChanges: { authorName?: string | null; dailyGoalWords?: number | null } = {};
    if (trimmedAtelierAuthor !== atelier.author_name) atelierChanges.authorName = trimmedAtelierAuthor;
    if (daily !== atelier.daily_goal_words) atelierChanges.dailyGoalWords = daily;

    // Nothing carried is no write — the pristine save closes honestly.
    if (Object.keys(changes).length === 0 && Object.keys(atelierChanges).length === 0) {
      onClose();
      return;
    }
    setError(false);
    try {
      if (Object.keys(changes).length > 0) await updateNovel.mutateAsync(changes);
      if (Object.keys(atelierChanges).length > 0) {
        await updateSettings.mutateAsync({ locale: atelier.locale, ...atelierChanges });
      }
      onClose();
    } catch {
      setError(true);
    }
  }

  function submitSeries() {
    const name = newName.trim();
    if (name === "" || createSeries.isPending) return;
    setCreateError(null);
    createSeries.mutate(
      { title: name },
      {
        onSuccess: (row) => {
          // The fresh row stands in the select at once — the cache carries
          // it until the invalidated list refetch lands the server's truth.
          queryClient.setQueryData<Series[]>(["series"], (old) => [...(old ?? []), row]);
          seriesTouched.current = true;
          setSeriesId(row.id);
          setCreating(false);
          setNewName("");
          setCreateError(null);
        },
        onError: (failure) =>
          setCreateError((failure as { status?: number }).status === 409 ? "duplicate" : "failed"),
      },
    );
  }

  const capBlocked = GENRE_PILL_DEFS.some(
    (pill) => !pills.includes(pill.value) && wouldOverflow(pills, pill.value),
  );
  const targetProgress = targetValue !== "invalid" ? progress(novel.word_count, targetValue) : null;
  const band = targetValue !== "invalid" && targetValue !== null ? wordBand(targetValue) : null;
  const canonName = canon !== null ? CANON_NAMES[canon] : undefined;
  const seriesOptions = series.data ?? [];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-scrim p-4 backdrop-blur-[1px]"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy && !dirty) onClose();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={headingId}
        className="flex max-h-[calc(100vh-2rem)] w-full max-w-5xl flex-col overflow-hidden rounded-xl border border-border bg-surface-container-low shadow-overlay"
      >
        {/* The pinned header — the tune chip, the title, the book's own
            chip, the Fertig cross (the dirty rule holds it). */}
        <header className="flex shrink-0 items-center justify-between gap-3 border-b border-border bg-panel px-7 py-4">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded border border-border bg-surface-container text-primary">
              <Icon name="tune" size={16} />
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2.5">
                <h2 id={headingId} className="text-title font-semibold text-foreground">
                  {t("writing.settings.title")}
                </h2>
                <span className={`${SERIF} inline-flex max-w-[220px] items-center gap-1.5 rounded-full border border-border bg-surface-container px-2.5 py-0.5 text-meta italic text-primary`}>
                  <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                  <span className="truncate" title={novel.title}>{novel.title}</span>
                </span>
              </div>
              <p className="mt-0.5 truncate text-meta text-muted">{t("writing.settings.subtitle")}</p>
            </div>
          </div>
          <button
            type="button"
            disabled={busy || dirty}
            // Label in Name (WCAG 2.5.3): the visible „Fertig" rides the
            // accessible name — the draft's aria-label alone would not
            // contain it (the axe gate measures the live DOM).
            aria-label={`${t("writing.settings.close")} (${t("writing.workspace.crud.close")})`}
            onClick={onClose}
            className={`flex shrink-0 items-center gap-2 rounded border border-border bg-surface-container-lowest px-3 py-1.5 text-label text-muted transition-colors hover:bg-surface-container hover:text-foreground ${FOCUS} ${busy || dirty ? "cursor-not-allowed opacity-50" : ""}`}
          >
            {t("writing.settings.close")}
            <Icon name="cross" size={13} />
          </button>
        </header>

        {/* The scrolling body — the five sections, the draft's divide. */}
        <div className="flex-1 space-y-7 overflow-y-auto p-7 [scrollbar-color:var(--color-outline-variant)_transparent] [scrollbar-width:thin]">
          {/* 1. Buch & Metadaten */}
          <section className="space-y-4">
            <SectionHead icon="menuBook" title={t("writing.settings.book.heading")} eyebrow={t("writing.settings.book.eyebrow")} />
            <div className="grid grid-cols-1 gap-4 md:grid-cols-12">
              <div className="md:col-span-7">
                <label htmlFor={`${headingId}-title`} className="mb-1.5 block text-label font-medium text-foreground">
                  {t("writing.settings.titleLabel")}
                </label>
                <input
                  id={`${headingId}-title`}
                  ref={titleRef}
                  type="text"
                  maxLength={200}
                  value={title}
                  aria-invalid={fieldErrors.title === true}
                  onChange={(event) => setTitle(event.target.value)}
                  className={`${INPUT} ${SERIF} text-lg text-primary ${fieldErrors.title ? "border-danger" : ""}`}
                />
                {fieldErrors.title && (
                  <p role="alert" className="mt-1 text-meta text-danger">
                    {t("writing.settings.titleRequired")}
                  </p>
                )}
              </div>
              <div className="md:col-span-5">
                <label htmlFor={`${headingId}-author`} className="mb-1.5 block text-label font-medium text-foreground">
                  {t("writing.settings.authorLabel")}
                </label>
                <input
                  id={`${headingId}-author`}
                  type="text"
                  maxLength={200}
                  value={author}
                  onChange={(event) => setAuthor(event.target.value)}
                  className={INPUT}
                />
                <p className="mt-1 text-meta text-muted">{t("writing.settings.authorNote")}</p>
              </div>
              <div className="md:col-span-8">
                <span id={`${headingId}-genre`} className="mb-1.5 block text-label font-medium text-foreground">
                  {t("writing.settings.genreLabel")}
                </span>
                <div role="group" aria-labelledby={`${headingId}-genre`} className="flex flex-wrap gap-2">
                  {GENRE_PILL_DEFS.map((pill) => {
                    const selected = pills.includes(pill.value);
                    const blocked = !selected && wouldOverflow(pills, pill.value);
                    return (
                      <button
                        key={pill.value}
                        type="button"
                        aria-pressed={selected}
                        disabled={blocked}
                        onClick={() =>
                          setPills((previous) =>
                            previous.includes(pill.value)
                              ? previous.filter((value) => value !== pill.value)
                              : [...previous, pill.value],
                          )
                        }
                        className={
                          selected
                            ? `inline-flex items-center gap-1.5 rounded border border-primary bg-primary px-3 py-1 text-label font-medium text-primary-foreground shadow-sm ${FOCUS}`
                            : blocked
                              ? "cursor-not-allowed rounded border border-border bg-surface-container-lowest px-3 py-1 text-label text-muted opacity-50"
                              : `rounded border border-border bg-surface-container-lowest px-3 py-1 text-label text-muted transition-colors hover:bg-surface-container hover:text-foreground ${FOCUS}`
                        }
                      >
                        {selected && <Icon name="check" size={13} />}
                        {t(pill.key)}
                      </button>
                    );
                  })}
                </div>
                {capBlocked && (
                  <p className="mt-1 text-meta text-muted">
                    {t("writing.shelf.dialog.genreCapNote", { cap: GENRE_CAP })}
                  </p>
                )}
              </div>
              <div className="md:col-span-4">
                <Segment
                  label={t("writing.settings.languageLabel")}
                  options={LANGUAGES.map((code) => ({ id: code, label: code.toUpperCase() }))}
                  value={language}
                  onChange={setLanguage}
                />
              </div>
              <div className="md:col-span-12">
                <div className="mb-1.5 flex items-center justify-between gap-2">
                  <label htmlFor={`${headingId}-blurb`} className="text-label font-medium text-foreground">
                    {t("writing.settings.blurbLabel")}
                  </label>
                  <span className="text-meta text-muted">{t("writing.settings.blurbNote")}</span>
                </div>
                <textarea
                  id={`${headingId}-blurb`}
                  rows={3}
                  value={blurb}
                  onChange={(event) => setBlurb(event.target.value)}
                  className={`${INPUT} h-auto resize-y p-3 leading-relaxed`}
                />
              </div>
            </div>
          </section>

          {/* 2. Status & Zielumfang */}
          <section className="space-y-4 border-t border-rule pt-6">
            <SectionHead icon="insights" title={t("writing.settings.status.heading")} eyebrow={t("writing.settings.status.eyebrow")} />
            <div className="grid grid-cols-1 items-start gap-5 md:grid-cols-12">
              <div className="md:col-span-5">
                <Segment
                  label={t("writing.settings.statusLabel")}
                  options={STATUSES.map((entry) => ({ id: entry.id, label: t(entry.label) }))}
                  value={status}
                  onChange={setStatus}
                />
                <p className="mt-1.5 text-meta text-muted">{t("writing.settings.chapterGoalNote")}</p>
              </div>
              <div className="md:col-span-7">
                <div className="mb-1.5 flex items-center justify-between gap-2">
                  <label htmlFor={`${headingId}-target`} className="text-label font-medium text-foreground">
                    {t("writing.settings.targetLabel")}
                  </label>
                  <span className="text-meta text-muted">{t("writing.settings.targetNote")}</span>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <div className="relative w-44">
                    <input
                      id={`${headingId}-target`}
                      type="text"
                      inputMode="numeric"
                      value={targetRaw}
                      aria-invalid={fieldErrors.target === true}
                      onChange={(event) => setTargetRaw(event.target.value)}
                      className={`${INPUT} pr-16 font-mono tabular-nums ${fieldErrors.target ? "border-danger" : ""}`}
                    />
                    <span className="pointer-events-none absolute right-3 top-2 text-meta text-muted">
                      {t("writing.settings.targetUnit")}
                    </span>
                  </div>
                  {band !== null && (
                    <span className="inline-flex items-center gap-2 rounded border border-border bg-surface-container-lowest px-3 py-1.5">
                      <span className="text-primary">
                        <Icon name="autoStories" size={15} />
                      </span>
                      <span className="text-meta font-medium text-foreground">
                        {t(BANDS[band].band)} ({t(BANDS[band].range)})
                      </span>
                    </span>
                  )}
                </div>
                {fieldErrors.target && (
                  <p role="alert" className="mt-1 text-meta text-danger">
                    {t("writing.settings.targetInvalid")}
                  </p>
                )}
                <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-container">
                  {targetProgress !== null && (
                    <div
                      data-testid="settings-target-progress"
                      className="h-full bg-primary"
                      style={{ width: `${targetProgress.width}%` }}
                    />
                  )}
                </div>
                <div className="mt-1 flex justify-between text-meta text-muted">
                  {targetProgress !== null ? (
                    <>
                      <span>{t("writing.settings.targetWritten", { count: novel.word_count })}</span>
                      <span>{t("writing.settings.targetPercent", { percent: targetProgress.percent })}</span>
                    </>
                  ) : (
                    <span>{t("writing.shelf.noTarget")}</span>
                  )}
                </div>
              </div>
            </div>
          </section>

          {/* 3. KI-Partner & Kausalitäts-Engine */}
          <section className="space-y-4 border-t border-rule pt-6">
            <SectionHead icon="hub" title={t("writing.settings.ai.heading")} eyebrow={t("writing.settings.ai.eyebrow")} />
            <div>
              <span id={`${headingId}-typology`} className="mb-1.5 block text-label font-medium text-foreground">
                {t("writing.settings.typologyLabel")}
              </span>
              <div
                role="radiogroup"
                aria-labelledby={`${headingId}-typology`}
                className="grid grid-cols-1 gap-3 md:grid-cols-3"
              >
                {TYPOLOGIES.map((entry, at) => {
                  const selected = typology === entry.id;
                  return (
                    <div
                      key={entry.id}
                      role="radio"
                      aria-checked={selected}
                      aria-labelledby={`${headingId}-typology-${entry.id}-label`}
                      tabIndex={selected || (typology === null && at === 0) ? 0 : -1}
                      ref={(node) => {
                        typologyRefs.current[entry.id] = node;
                      }}
                      onClick={() => setTypology(entry.id)}
                      onKeyDown={(event) =>
                        radioKey(event, TYPOLOGIES.map((row) => row.id), at, setTypology, typologyRefs)
                      }
                      className={`cursor-pointer space-y-1 rounded border p-3 transition-colors ${FOCUS} ${
                        selected
                          ? "border-2 border-primary bg-surface-container"
                          : "border-border bg-surface-container-lowest hover:bg-surface-container"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span
                          id={`${headingId}-typology-${entry.id}-label`}
                          className={`text-label font-semibold ${selected ? "text-primary" : "text-foreground"}`}
                        >
                          {t(entry.label)}
                        </span>
                        <span
                          aria-hidden="true"
                          className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full border ${
                            selected ? "border-primary bg-primary text-primary-foreground" : "border-border"
                          }`}
                        >
                          {selected && <Icon name="check" size={11} />}
                        </span>
                      </div>
                      <p className={`text-meta leading-snug ${selected ? "font-medium text-foreground" : "text-muted"}`}>
                        {t(entry.body)}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
            <div>
              <label htmlFor={`${headingId}-form`} className="mb-1.5 block text-label font-medium text-foreground">
                {t("writing.settings.formLabel")}
              </label>
              <div className="relative md:w-1/2">
                <select
                  id={`${headingId}-form`}
                  value={form}
                  onChange={(event) => setForm(event.target.value)}
                  className={`${INPUT} appearance-none pr-8`}
                >
                  <option value="">{t("writing.settings.formNone")}</option>
                  {FORMS.map((entry) => (
                    <option key={entry.id} value={entry.id}>
                      {t(entry.label)}
                    </option>
                  ))}
                </select>
                <span className="pointer-events-none absolute right-2.5 top-2.5 text-muted">
                  <Icon name="selectChevron" size={14} />
                </span>
              </div>
            </div>
            <div>
              <span id={`${headingId}-role`} className="mb-1.5 block text-label font-medium text-foreground">
                {t("writing.settings.roleLabel")}
              </span>
              <div
                role="radiogroup"
                aria-labelledby={`${headingId}-role`}
                className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-4"
              >
                {ROLES.map((entry, at) => {
                  const selected = role === entry.id;
                  return (
                    <div
                      key={entry.id}
                      role="radio"
                      aria-checked={selected}
                      aria-labelledby={`${headingId}-role-${entry.id}-label`}
                      tabIndex={selected || (role === null && at === 0) ? 0 : -1}
                      ref={(node) => {
                        roleRefs.current[entry.id] = node;
                      }}
                      onClick={() => setRole(entry.id)}
                      onKeyDown={(event) => radioKey(event, ROLES.map((row) => row.id), at, setRole, roleRefs)}
                      className={`cursor-pointer rounded border p-2.5 transition-colors ${FOCUS} ${
                        selected
                          ? "border-2 border-primary bg-surface-container"
                          : "border-border bg-surface-container-lowest hover:bg-surface-container"
                      }`}
                    >
                      <div className="mb-0.5 flex items-center justify-between gap-1">
                        <span
                          id={`${headingId}-role-${entry.id}-label`}
                          className={`text-label font-semibold ${selected ? "text-primary" : "text-foreground"}`}
                        >
                          {t(entry.label)}
                        </span>
                        {selected && (
                          <span className="shrink-0 text-primary">
                            <Icon name="check" size={13} />
                          </span>
                        )}
                      </div>
                      <p className={`text-meta leading-snug ${selected ? "font-medium text-foreground" : "text-muted"}`}>
                        {t(entry.meta)}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
            <div className="space-y-3 rounded border border-border bg-surface-container-lowest p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <label htmlFor={`${headingId}-canon`} className="block text-label font-semibold text-foreground">
                    {t("writing.settings.canonLabel")}
                  </label>
                  <p className="text-meta text-muted">{t("writing.settings.canonQuestion")}</p>
                </div>
                <span className="inline-flex items-center rounded border border-border bg-surface-container px-2.5 py-0.5 text-meta font-semibold text-primary">
                  {canon === null
                    ? t("writing.settings.canonUnset")
                    : canonName !== undefined
                      ? t("writing.settings.canonBadgeNamed", { n: canon, name: t(canonName) })
                      : t("writing.settings.canonBadge", { n: canon })}
                </span>
              </div>
              <div className="space-y-1.5 pt-1">
                <input
                  id={`${headingId}-canon`}
                  type="range"
                  min={1}
                  max={5}
                  step={1}
                  value={canon ?? 3}
                  onChange={(event) => setCanon(Number(event.target.value))}
                  className={`h-2 w-full cursor-pointer accent-primary ${FOCUS}`}
                />
                <div className="flex justify-between gap-2 px-0.5 text-meta text-muted">
                  <span>{t("writing.settings.canonStop1")}</span>
                  <span className="hidden sm:inline">{t("writing.settings.canonStop3")}</span>
                  <span className="text-right">{t("writing.settings.canonStop5")}</span>
                </div>
              </div>
            </div>
          </section>

          {/* 4. Reihe & Serien-Kontext */}
          <section className="space-y-4 border-t border-rule pt-6">
            <SectionHead icon="bookmarkCollection" title={t("writing.settings.series.heading")} eyebrow={t("writing.settings.series.eyebrow")} />
            <div className="grid grid-cols-1 items-end gap-4 md:grid-cols-12">
              <div className="md:col-span-6">
                <label htmlFor={`${headingId}-series`} className="mb-1.5 block text-label font-medium text-foreground">
                  {t("writing.settings.seriesLabel")}
                </label>
                <div className="relative">
                  <select
                    id={`${headingId}-series`}
                    value={seriesId ?? ""}
                    onChange={(event) => {
                      seriesTouched.current = true;
                      const next = event.target.value === "" ? null : event.target.value;
                      setSeriesId(next);
                      // Leaving the series takes the volume's face with it.
                      if (next === null) setVolumeRaw("");
                    }}
                    className={`${INPUT} appearance-none pr-8`}
                  >
                    <option value="">{t("writing.settings.seriesNone")}</option>
                    {seriesOptions.map((row) => (
                      <option key={row.id} value={row.id}>
                        {row.title}
                      </option>
                    ))}
                  </select>
                  <span className="pointer-events-none absolute right-2.5 top-2.5 text-muted">
                    <Icon name="selectChevron" size={14} />
                  </span>
                </div>
              </div>
              <div className="md:col-span-2">
                <label htmlFor={`${headingId}-volume`} className="mb-1.5 block text-label font-medium text-foreground">
                  {t("writing.settings.volumeLabel")}
                </label>
                <input
                  id={`${headingId}-volume`}
                  type="text"
                  inputMode="numeric"
                  disabled={seriesId === null}
                  value={volumeRaw}
                  aria-invalid={fieldErrors.volume === true}
                  onChange={(event) => setVolumeRaw(event.target.value)}
                  className={`${INPUT} text-center font-mono tabular-nums ${fieldErrors.volume ? "border-danger" : ""} ${seriesId === null ? "cursor-not-allowed opacity-50" : ""}`}
                />
              </div>
              <div className="md:col-span-4">
                {creating ? (
                  <div className="space-y-1.5">
                    <label htmlFor={`${headingId}-new-series`} className="block text-label font-medium text-foreground">
                      {t("writing.settings.seriesCreateLabel")}
                    </label>
                    <div className="flex items-center gap-2">
                      <input
                        id={`${headingId}-new-series`}
                        type="text"
                        maxLength={200}
                        value={newName}
                        autoFocus
                        onChange={(event) => setNewName(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            event.preventDefault();
                            submitSeries();
                          }
                        }}
                        className={INPUT}
                      />
                      <button
                        type="button"
                        disabled={newName.trim() === "" || createSeries.isPending}
                        onClick={submitSeries}
                        className={`inline-flex h-9 shrink-0 items-center gap-1.5 rounded bg-primary px-3 text-label font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS} ${newName.trim() === "" || createSeries.isPending ? "cursor-not-allowed opacity-60" : ""}`}
                      >
                        {createSeries.isPending && <Spinner />}
                        {t("writing.settings.seriesCreateConfirm")}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setCreating(false);
                          setNewName("");
                          setCreateError(null);
                        }}
                        className={`h-9 shrink-0 rounded border border-border px-2.5 text-label text-muted transition-colors hover:bg-surface-container ${FOCUS}`}
                      >
                        {t("writing.workspace.crud.cancel")}
                      </button>
                    </div>
                    {createError && (
                      <p role="alert" className="text-meta text-danger">
                        {t(
                          createError === "duplicate"
                            ? "writing.settings.seriesDuplicate"
                            : "writing.settings.seriesCreateError",
                        )}
                      </p>
                    )}
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => setCreating(true)}
                    className={`flex h-9 w-full items-center justify-center gap-1.5 rounded border border-dashed border-border bg-surface-container-lowest text-label text-muted transition-colors hover:bg-surface-container hover:text-foreground ${FOCUS}`}
                  >
                    <Icon name="plus" size={14} />
                    {t("writing.settings.seriesCreate")}
                  </button>
                )}
              </div>
              <div className="md:col-span-12">
                {series.isError ? (
                  <ErrorLine message={t("writing.settings.seriesLoadError")} onRetry={() => void series.refetch()} />
                ) : (
                  <p className="text-meta text-muted">{t("writing.settings.seriesNote")}</p>
                )}
                {fieldErrors.volume && (
                  <p role="alert" className="mt-1 text-meta text-danger">
                    {t("writing.settings.volumeInvalid")}
                  </p>
                )}
              </div>
            </div>
          </section>

          {/* 5. Atelier & Globale Autorenebene */}
          <section className="space-y-4 border-t border-rule pt-6">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <span className="text-primary">
                  <Icon name="person" size={17} />
                </span>
                <h3 className="text-emph font-semibold text-foreground">{t("writing.settings.atelier.heading")}</h3>
                <span className="inline-flex items-center rounded-full bg-secondary-container px-2 py-0.5 text-meta font-semibold text-secondary-container-foreground">
                  {t("writing.settings.atelier.badge")}
                </span>
              </div>
              <span className="text-eyebrow font-semibold uppercase tracking-wider text-muted">
                {t("writing.settings.atelier.eyebrow")}
              </span>
            </div>
            <div className="rounded border border-border bg-surface-container p-4">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div>
                  <label htmlFor={`${headingId}-atelier-author`} className="mb-1.5 block text-label font-medium text-foreground">
                    {t("writing.settings.atelierAuthorLabel")}
                  </label>
                  <input
                    id={`${headingId}-atelier-author`}
                    type="text"
                    maxLength={200}
                    value={atelierAuthor}
                    onChange={(event) => setAtelierAuthor(event.target.value)}
                    className={INPUT}
                  />
                  <p className="mt-1 text-meta text-muted">{t("writing.settings.atelierAuthorNote")}</p>
                </div>
                <div>
                  <label htmlFor={`${headingId}-daily`} className="mb-1.5 block text-label font-medium text-foreground">
                    {t("writing.settings.dailyGoalLabel")}
                  </label>
                  <div className="relative">
                    <input
                      id={`${headingId}-daily`}
                      type="text"
                      inputMode="numeric"
                      value={dailyRaw}
                      aria-invalid={fieldErrors.daily === true}
                      onChange={(event) => setDailyRaw(event.target.value)}
                      className={`${INPUT} pr-16 font-mono tabular-nums ${fieldErrors.daily ? "border-danger" : ""}`}
                    />
                    <span className="pointer-events-none absolute right-3 top-2 text-meta text-muted">
                      {t("writing.settings.targetUnit")}
                    </span>
                  </div>
                  {fieldErrors.daily ? (
                    <p role="alert" className="mt-1 text-meta text-danger">
                      {t("writing.settings.dailyGoalInvalid")}
                    </p>
                  ) : (
                    <p className="mt-1 text-meta text-muted">{t("writing.settings.dailyGoalNote")}</p>
                  )}
                </div>
              </div>
            </div>
          </section>
        </div>

        {/* The pinned footer — the inheritance note (true now), the error
            line above the actions, Abbrechen and Speichern. */}
        <div className="shrink-0 border-t border-border bg-panel">
          {error && (
            <div className="px-7 pt-3">
              <ErrorLine message={t("writing.settings.error")} onRetry={() => void save()} />
            </div>
          )}
          <footer className="flex flex-col items-center justify-between gap-3 px-7 py-4 sm:flex-row">
            <div className="flex items-center gap-2 text-meta text-muted">
              <span className="text-primary">
                <Icon name="spark" size={15} />
              </span>
              <span>{t("writing.settings.inheritance")}</span>
            </div>
            <div className="flex w-full items-center justify-end gap-3 sm:w-auto">
              <button
                type="button"
                disabled={busy}
                onClick={onClose}
                className={`rounded border border-border bg-surface-container-lowest px-4 py-1.5 text-label text-foreground transition-colors hover:bg-surface-container ${FOCUS} ${busy ? "cursor-not-allowed opacity-50" : ""}`}
              >
                {t("writing.workspace.crud.cancel")}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void save()}
                className={`inline-flex items-center gap-1.5 rounded bg-primary px-5 py-1.5 text-label font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS} ${busy ? "cursor-not-allowed opacity-60" : ""}`}
              >
                {busy ? <Spinner /> : <Icon name="check" size={14} />}
                {busy ? t("writing.settings.busy") : t("writing.workspace.crud.save")}
              </button>
            </div>
          </footer>
        </div>
      </div>
    </div>
  );
}
