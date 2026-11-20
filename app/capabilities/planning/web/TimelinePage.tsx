/**
 * The chronology page (W6 Task 3) — the planning capability's first web
 * surface, ported from the owner-approved harmonized `chronology-timeline-2`
 * draft onto the shell's tokens. The novel's real TimelineEventRead rows in
 * the server's manual order:
 *
 * - Two sections per the draft's geometry: the positioned rows first
 *   („Chronologisch geordnete Ereignisse", the server's own order —
 *   position asc, nulls last, creation breaking ties), the unordered rows
 *   (null position) in the second section at the end, with the draft's
 *   dashed „undatiertes Ereignis anlegen" placeholder as its last card.
 * - The cards carry only real fields: the free-text date (mono) or the
 *   honest „Kein Datum", the title, the description excerpt, the
 *   free-text name chips and the chapter chip — plain text naming the
 *   chapter, never a link: the workspace route carries no chapter param,
 *   and a door that lands wherever the workspace last stood is a
 *   half-truth (a chapter that no longer resolves says „Kein Kapitel";
 *   the model SET NULLs on the server, and a stale list must not
 *   out-lie it). The draft's invented relative-time badges („Vor 9 J."),
 *   the „Entwurf" badge (no field carries it) and the bottom PDF/export
 *   dock (no backend) are not ported.
 * - Editing rides the house dialog family (timelineDialogs): a card opens
 *   the edit, the header and the placeholder open the create, the edit's
 *   foot hands off to the delete confirm.
 * - The name-chip filter composes with the quick filters (Alle / Mit
 *   Kapitel / Ohne Datum) — AND across the two kinds, OR within the
 *   names. The draft's „Kapitelabfolge" view toggle has no drawn face in
 *   any draft, so it waits honestly disabled with its note (the gap-
 *   ledger pattern).
 * - The scene-status counters derive from the per-chapter fan-out
 *   (`useNovelScenes`): every real status counted (verfasst, in Arbeit,
 *   geplant) plus the events' own honest „ohne Datum" count. A failed
 *   fan-out invents no numbers — the counters simply do not stand.
 * - The subbar with the sub-nav sibling doors (the drafts' mechanism:
 *   Chronologie / Storyboard / Kausalitätsleiste) stands in EVERY state —
 *   pending, outage, empty, populated (W5 #923's rule); only the body
 *   below it varies.
 *
 * The page reads the real API through the shell's query seam and imports
 * no other capability (rule 1).
 */
import { useNavigate, useParams } from "@tanstack/react-router";
import { useMemo, useState } from "react";

import { useTranslation } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import { useChaptersQuery, useNovelScenes, useTimelineEvents } from "@shell/lib/query";
import { FOCUS } from "@shell/ui/card";
import { Icon } from "@shell/ui/icons";

import type { TimelineEvent } from "@shell/lib/api/client";
import { CreateEventDialog, DeleteEventDialog, EditEventDialog } from "./timelineDialogs";

const STORYBOARD_PATH = "/novels/$novelId/planning/storyboard";
const CAUSALITY_PATH = "/novels/$novelId/planning/causality";

/** The quick filters — the draft's segmented control's three states. */
type QuickFilter = "all" | "withChapter" | "withoutDate";

/** The open dialog, one at a time: a create, an edit, or the destructive
 *  confirm the edit hands off to. */
type Dialog =
  | { kind: "create"; openerId: string }
  | { kind: "edit"; event: TimelineEvent; openerId: string }
  | { kind: "delete"; event: TimelineEvent; openerId: string };

/** The draft's chip faces on the shell's tokens: a rounded mark of the
 *  meta register, primary-lifted when the filter it carries is on. */
function chipClass(active: boolean): string {
  return `rounded-[var(--radius-control)] px-2 py-0.5 text-meta transition-colors ${FOCUS} ${
    active ? "bg-primary/15 font-semibold text-primary" : "bg-surface-container text-foreground hover:bg-secondary/15"
  }`;
}

export function TimelinePage() {
  const t = useTranslation();
  const { novelId } = useParams({ from: "/novels/$novelId/planning/timeline" });
  const navigate = useNavigate();
  usePageTitle(t("planning.timeline.title"));

  const events = useTimelineEvents(novelId);
  const chapters = useChaptersQuery(novelId);
  const chapterList = useMemo(() => chapters.data ?? [], [chapters.data]);
  const scenes = useNovelScenes(chapterList);

  const [selectedNames, setSelectedNames] = useState<string[]>([]);
  const [quick, setQuick] = useState<QuickFilter>("all");
  const [dialog, setDialog] = useState<Dialog | null>(null);

  const eventList = useMemo(() => events.data ?? [], [events.data]);

  // The name chips' population: every distinct name the novel's events
  // carry, first-seen order — read from the unfiltered list so the chips
  // never move under the filter they narrow.
  const knownNames = useMemo(() => {
    const seen: string[] = [];
    for (const event of eventList) {
      for (const name of event.character_names) {
        if (!seen.includes(name)) seen.push(name);
      }
    }
    return seen;
  }, [eventList]);

  // The filter: OR within the selected names, AND with the quick filter.
  const visible = useMemo(() => {
    const names = new Set(selectedNames);
    return eventList.filter((event) => {
      if (names.size > 0 && !event.character_names.some((name) => names.has(name))) return false;
      if (quick === "withChapter" && event.chapter_id === null) return false;
      if (quick === "withoutDate" && event.date_label !== "") return false;
      return true;
    });
  }, [eventList, selectedNames, quick]);

  // The draft's two sections: positioned rows first, null positions last —
  // the server already answers in that order, so the page partitions
  // without re-sorting (the canvas order the writer arranged is the
  // server's own).
  const ordered = visible.filter((event) => event.position !== null);
  const unordered = visible.filter((event) => event.position === null);

  // The chapter chip's words resolve through the chapters list — a
  // chapter_id nothing resolves to is not named at all (SET NULL is the
  // server's own answer; a stale list must not out-lie it with a dead
  // link).
  const chapterById = useMemo(
    () => new Map(chapterList.map((chapter) => [chapter.id, chapter])),
    [chapterList],
  );

  // The scene-status counters: every real status of the lifecycle, counted
  // across the whole fan. Only a complete, error-free fan may count — a
  // chapters outage empties the list and the vacuous fan would read as
  // „0 Szenen", and a half-current novel invents numbers otherwise.
  const counters = useMemo(() => {
    if (!chapters.isSuccess || !scenes.isSuccess || scenes.data === undefined) return null;
    let complete = 0;
    let inProgress = 0;
    let planned = 0;
    for (const aggregate of scenes.data) {
      for (const scene of aggregate.scenes) {
        if (scene.status === "complete") complete += 1;
        else if (scene.status === "in_progress") inProgress += 1;
        else planned += 1;
      }
    }
    const withoutDate = eventList.filter((event) => event.date_label === "").length;
    return { complete, inProgress, planned, withoutDate };
  }, [chapters.isSuccess, scenes.isSuccess, scenes.data, eventList]);

  const pending = events.isPending;
  const failed = events.isError;

  function clearFilters() {
    setSelectedNames([]);
    setQuick("all");
  }

  function toggleName(name: string) {
    setSelectedNames((previous) =>
      previous.includes(name) ? previous.filter((standing) => standing !== name) : [...previous, name],
    );
  }

  /** The chapter chip's words: the plain number on an ordered row, the
   *  draft's „Geplant Kapitel N" on an unordered one — the plan is a real
   *  field even where the order is not yet. */
  function chapterChipWords(position: number, unorderedCard: boolean): string {
    return t(
      unorderedCard ? "planning.timeline.plannedChapterChip" : "planning.timeline.chapterChip",
      { position: position + 1 },
    );
  }

  /** One event card — the draft's geometry: the mono date over the serif
   *  title and the clamped excerpt, the names and the chapter chip in the
   *  foot. The card's body is the edit affordance; the chip stands outside
   *  it (a control never nests in a button). */
  function card(event: TimelineEvent, unorderedCard: boolean) {
    const chapter = event.chapter_id === null ? undefined : chapterById.get(event.chapter_id);
    const openerId = `timeline-card-${event.id}`;
    return (
      <article
        key={event.id}
        data-testid="timeline-card"
        className={`flex flex-col rounded-[var(--radius-surface)] p-3.5 text-left shadow-card transition-colors ${
          unorderedCard
            ? "border border-dashed border-border bg-surface-container-low/60"
            : "border border-rule bg-card hover:bg-surface-container-low"
        }`}
      >
        <button
          type="button"
          id={openerId}
          onClick={() => setDialog({ kind: "edit", event, openerId })}
          className={`flex flex-1 flex-col text-left ${FOCUS}`}
        >
          <span className="mb-2 flex items-center justify-between gap-2">
            <span className="font-mono text-meta font-bold text-outline">
              {event.date_label !== "" ? event.date_label : t("planning.timeline.noDate")}
            </span>
          </span>
          <span className="[font-family:var(--font-serif)] line-clamp-2 text-label font-semibold leading-snug text-foreground">
            {event.title}
          </span>
          {event.description.trim() !== "" && (
            <span className="mt-1.5 line-clamp-3 text-meta leading-relaxed text-muted">
              {event.description}
            </span>
          )}
        </button>
        <span className="mt-3 flex flex-wrap items-center justify-between gap-1.5 border-t border-rule pt-2.5 text-meta">
          <span className="flex flex-wrap gap-1">
            {event.character_names.map((name) => (
              <span key={name} className="rounded-[var(--radius-control)] bg-surface-container px-1.5 py-0.5 text-foreground">
                {name}
              </span>
            ))}
          </span>
          {chapter !== undefined ? (
            // Plain text, not a door: the workspace route knows no chapter
            // param, and a link that lands anywhere but the chapter it
            // names would be a half-true navigation control.
            <span className="rounded-[var(--radius-control)] bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary">
              {chapterChipWords(chapter.position, unorderedCard)}
            </span>
          ) : event.chapter_id !== null && chapters.isError ? (
            // The row names a chapter the unreadable list cannot resolve —
            // that is unknown, not absent, and never a guess.
            <span className="rounded-[var(--radius-control)] bg-surface-container px-1.5 py-0.5 text-muted">
              {t("planning.timeline.chapterUnknown")}
            </span>
          ) : (
            <span className="rounded-[var(--radius-control)] bg-surface-container px-1.5 py-0.5 text-muted">
              {t("planning.timeline.noChapter")}
            </span>
          )}
        </span>
      </article>
    );
  }

  return (
    <div
      id="timeline-page"
      data-testid="timeline-page"
      tabIndex={-1}
      className="flex h-full flex-col overflow-hidden focus:outline-none"
    >
      {/* The subbar — the page chip, the sub-nav sibling doors (the drafts'
          mechanism), the create door, and the filters row. One consistent
          mechanism with the knowledge surfaces: the bar stands in EVERY
          state — pending, failed, empty, populated — so the sibling doors
          never vanish behind an honest face; only the body below varies. */}
      <div className="flex shrink-0 flex-col gap-2 border-b border-border bg-surface-container-low px-4 py-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="flex items-center gap-1.5 rounded-full border border-rule bg-card px-3 py-1 text-meta font-semibold text-foreground shadow-card">
              <span className="text-primary">
                <Icon name="planning" size={15} />
              </span>
              {t("planning.timeline.title")}
            </span>
            {/* The sub-nav doors — the drafts' Chronologie / Storyboard /
                Kausalitätsleiste. The siblings' surfaces land with their
                own tasks this wave; the routes stand, so the doors walk. */}
            <button
              type="button"
              data-testid="timeline-storyboard-door"
              onClick={() => {
                void navigate({ to: STORYBOARD_PATH, params: { novelId }, search: {} });
              }}
              className={`flex items-center gap-1.5 rounded-full border border-rule bg-card px-3 py-1 text-meta text-foreground shadow-card transition-colors hover:bg-surface-container ${FOCUS}`}
            >
              <Icon name="viewList" size={14} /> {t("planning.sub.storyboard")}
            </button>
            <button
              type="button"
              data-testid="timeline-causality-door"
              onClick={() => {
                void navigate({ to: CAUSALITY_PATH, params: { novelId }, search: {} });
              }}
              className={`flex items-center gap-1.5 rounded-full border border-rule bg-card px-3 py-1 text-meta text-foreground shadow-card transition-colors hover:bg-surface-container ${FOCUS}`}
            >
              <Icon name="waves" size={14} /> {t("planning.sub.causality")}
            </button>
          </div>
          <button
            type="button"
            id="timeline-new-event"
            onClick={() => setDialog({ kind: "create", openerId: "timeline-new-event" })}
            className={`inline-flex items-center gap-1.5 rounded-[var(--radius-control)] bg-primary px-3 py-1 text-meta font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS}`}
          >
            <Icon name="plus" size={14} /> {t("planning.timeline.newEvent")}
          </button>
        </div>
        {/* The filters row: the name chips (the events' own free-text
            names), the quick filters, and the chapter-sequence view — an
            honest disabled gap: no draft drew its face. */}
        <div className="flex flex-wrap items-center justify-between gap-2 pt-0.5">
          <div className="flex flex-wrap items-center gap-2">
            <span
              data-testid="timeline-name-filters"
              className="flex flex-wrap items-center gap-1.5 rounded-[var(--radius-control)] border border-rule bg-card px-2.5 py-1 shadow-card"
            >
              <span className="text-muted">
                <Icon name="tune" size={14} />
              </span>
              <span className="text-meta text-muted">{t("planning.timeline.filterLabel")}</span>
              {knownNames.map((name) => (
                <button
                  key={name}
                  type="button"
                  aria-pressed={selectedNames.includes(name)}
                  onClick={() => toggleName(name)}
                  className={chipClass(selectedNames.includes(name))}
                >
                  {name}
                </button>
              ))}
            </span>
            <div className="flex items-center rounded-[var(--radius-control)] border border-rule bg-card px-1 py-0.5 shadow-card">
              {(
                [
                  ["all", t("planning.timeline.all")],
                  ["withChapter", t("planning.timeline.withChapter")],
                  ["withoutDate", t("planning.timeline.withoutDate")],
                ] as const
              ).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  aria-pressed={quick === key}
                  onClick={() => setQuick(key)}
                  className={`rounded-[calc(var(--radius-control)-2px)] px-2.5 py-0.5 text-meta font-semibold transition-colors ${FOCUS} ${
                    quick === key ? "bg-surface-container text-primary" : "text-muted hover:text-foreground"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            {/* The draft's view toggle, drawn but never faced: the
                chapter-sequence view waits until a draft draws it — an
                honest gap with its note, never an invented face. */}
            <div data-testid="timeline-sequence-gap" aria-disabled="true" className="flex items-center gap-1.5 opacity-60">
              <button
                type="button"
                disabled
                title={t("planning.timeline.chapterSequenceNote")}
                className="flex cursor-not-allowed items-center gap-1.5 rounded-[var(--radius-control)] border border-rule bg-card px-2.5 py-1 text-meta text-muted shadow-card"
              >
                <Icon name="menuBook" size={14} /> {t("planning.timeline.chapterSequence")}
              </button>
              <span className="text-meta text-muted">{t("planning.timeline.chapterSequenceNote")}</span>
            </div>
          </div>
          {chapters.isError && (
            <p role="note" className="text-meta text-muted">
              {t("planning.timeline.chaptersUnavailable")}
            </p>
          )}
        </div>
      </div>

      {/* The body — the honest state's own face; the bar above stays. */}
      {pending ? (
        <div className="flex min-h-0 flex-1 items-center justify-center">
          <p role="status" className="text-body text-muted">
            {t("planning.timeline.loading")}
          </p>
        </div>
      ) : failed ? (
        <div className="flex min-h-0 flex-1 items-center justify-center p-6">
          <div role="alert" className="space-y-2 rounded-[var(--radius-surface)] border border-danger/40 bg-panel p-5 text-center">
            <p className="text-body text-danger">{t("planning.timeline.loadFailed")}</p>
            <button
              type="button"
              onClick={() => {
                void events.refetch();
                void chapters.refetch();
                void scenes.refetch();
              }}
              className={`rounded border border-border bg-surface-container-low px-3 py-1.5 text-meta font-medium text-foreground transition-colors hover:bg-surface-container ${FOCUS}`}
            >
              {t("planning.timeline.retry")}
            </button>
          </div>
        </div>
      ) : eventList.length === 0 ? (
        <div className="flex min-h-0 flex-1 items-center justify-center p-6">
          <div data-testid="timeline-empty" className="max-w-sm space-y-2 rounded-[var(--radius-surface)] border border-border bg-panel p-8 text-center">
            <span className="inline-block text-muted">
              <Icon name="planning" size={28} />
            </span>
            <p className="text-body font-semibold text-foreground">{t("planning.timeline.empty")}</p>
            <p className="text-meta text-muted">{t("planning.timeline.emptyNote")}</p>
          </div>
        </div>
      ) : visible.length === 0 ? (
        <div className="flex min-h-0 flex-1 items-center justify-center p-6">
          <div data-testid="timeline-no-results" className="max-w-sm space-y-2 rounded-[var(--radius-surface)] border border-border bg-panel p-6 text-center">
            <p className="text-meta text-muted">{t("planning.timeline.noResults")}</p>
            <button
              type="button"
              onClick={clearFilters}
              className={`rounded border border-border bg-surface-container-low px-3 py-1.5 text-meta font-medium text-foreground transition-colors hover:bg-surface-container ${FOCUS}`}
            >
              {t("planning.timeline.clearFilters")}
            </button>
          </div>
        </div>
      ) : (
        /* The draft's board: the summary bar with the scene counters, then
           the two sections. Below lg the whole body scrolls. */
        <div className="min-h-0 flex-1 overflow-y-auto bg-surface-container-low/30 p-4">
          <div className="mx-auto flex max-w-6xl flex-col gap-4">
            {/* The summary bar — the board's mechanism sentence and the
                counters; the sections below name themselves. */}
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-surface)] border border-rule bg-card px-4 py-2.5 shadow-card">
              <div className="flex items-center gap-2.5">
                <span aria-hidden="true" className="h-3 w-3 rounded-full bg-primary" />
                <span className="text-label font-semibold text-foreground">{t("planning.timeline.subtitle")}</span>
              </div>
              {counters !== null ? (
                <div
                  data-testid="timeline-counters"
                  aria-label={t("planning.timeline.scenesLabel")}
                  className="flex flex-wrap items-center gap-3 text-meta text-muted"
                >
                  <span className="flex items-center gap-1">
                    <span aria-hidden="true" className="h-2 w-2 rounded-full bg-success" />
                    {t("planning.timeline.scenesComplete", { count: counters.complete })}
                  </span>
                  <span className="flex items-center gap-1">
                    <span aria-hidden="true" className="h-2 w-2 rounded-full bg-warning" />
                    {t("planning.timeline.scenesInProgress", { count: counters.inProgress })}
                  </span>
                  <span className="flex items-center gap-1">
                    <span aria-hidden="true" className="h-2 w-2 rounded-full bg-primary" />
                    {t("planning.timeline.scenesPlanned", { count: counters.planned })}
                  </span>
                  <span className="flex items-center gap-1">
                    <span aria-hidden="true" className="h-2 w-2 rounded-full bg-outline" />
                    {t("planning.timeline.eventsWithoutDate", { count: counters.withoutDate })}
                  </span>
                </div>
              ) : (
                (scenes.isError || chapters.isError) && (
                  // A failed fan-out — or a chapters outage, whose empty
                  // fan would read as zeros — invents no numbers: the
                  // muted outage note stands where the counters stand,
                  // named by the region's own label, and its retry re-asks
                  // the chapters and the fan in place — no remount needed.
                  <div
                    data-testid="timeline-counters-outage"
                    className="flex items-center gap-2 text-meta text-muted"
                  >
                    <span aria-hidden="true" className="text-warning">
                      <Icon name="warning" size={13} />
                    </span>
                    <span>
                      {t("planning.timeline.scenesLabel")}: {t("planning.timeline.scenesOutage")}
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        void chapters.refetch();
                        void scenes.refetch();
                      }}
                      className={`font-medium text-primary underline underline-offset-2 transition-colors hover:text-foreground ${FOCUS}`}
                    >
                      {t("planning.timeline.retry")}
                    </button>
                  </div>
                )
              )}
            </div>

            {/* The board — the draft's rounded canvas. */}
            <div className="flex flex-col gap-6 rounded-[var(--radius-surface)] border border-rule bg-card p-4 shadow-card">
              {/* The positioned section: the server's order is the canvas
                  order — no client re-sort. */}
              <section data-testid="timeline-ordered" aria-label={t("planning.timeline.orderedSection")} className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <h2 className="rounded-[var(--radius-control)] bg-surface-container-high px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider text-primary">
                    {t("planning.timeline.orderedSection")}
                  </h2>
                  <span className="text-meta text-muted">
                    {t("planning.timeline.orderedCount", { count: ordered.length })}
                  </span>
                </div>
                <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2 xl:grid-cols-3">
                  {ordered.map((event) => card(event, false))}
                </div>
              </section>

              {/* The unordered section: fragments without a fixed position,
                  standing at the end — the draft's dashed register, its
                  add-note door, and the undated placeholder card. */}
              <section
                data-testid="timeline-unordered"
                aria-label={t("planning.timeline.unorderedSection")}
                className="flex flex-col gap-3 border-t border-rule pt-4"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="rounded-[var(--radius-control)] bg-surface-container px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider text-muted">
                      {t("planning.timeline.unorderedSection")}
                    </h2>
                    <span className="text-meta text-muted">{t("planning.timeline.unorderedNote")}</span>
                  </div>
                  <button
                    type="button"
                    id="timeline-add-note"
                    onClick={() => setDialog({ kind: "create", openerId: "timeline-add-note" })}
                    className={`inline-flex items-center gap-1 text-meta font-semibold text-primary underline-offset-2 transition-colors hover:underline ${FOCUS}`}
                  >
                    <Icon name="plus" size={13} /> {t("planning.timeline.addNote")}
                  </button>
                </div>
                <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2 xl:grid-cols-3">
                  {unordered.map((event) => card(event, true))}
                  <button
                    type="button"
                    id="timeline-new-undated"
                    onClick={() => setDialog({ kind: "create", openerId: "timeline-new-undated" })}
                    className={`flex min-h-28 flex-col items-center justify-center gap-1 rounded-[var(--radius-surface)] border border-dashed border-border bg-surface-container-low/50 p-6 text-center text-muted transition-colors hover:border-outline ${FOCUS}`}
                  >
                    <span className="text-outline">
                      <Icon name="plus" size={22} />
                    </span>
                    <span className="text-label font-medium text-foreground">{t("planning.timeline.newUndated")}</span>
                    <span className="text-[11px] text-muted">{t("planning.timeline.newUndatedNote")}</span>
                  </button>
                </div>
              </section>
            </div>
          </div>
        </div>
      )}

      {/* The dialogs — one lead at a time; the edit's foot hands the row to
          the confirm, and the edit WAITS beneath it (suspended, its state
          kept) so the confirm's cancel restores the form with its answers. */}
      {dialog?.kind === "create" && (
        <CreateEventDialog
          novelId={novelId}
          chapters={chapterList}
          openerId={dialog.openerId}
          onClose={() => setDialog(null)}
        />
      )}
      {(dialog?.kind === "edit" || dialog?.kind === "delete") && (
        <EditEventDialog
          event={dialog.event}
          chapters={chapterList}
          openerId={dialog.openerId}
          onClose={() => setDialog(null)}
          onRemove={(event) => setDialog({ kind: "delete", event, openerId: dialog.openerId })}
          suspended={dialog.kind === "delete"}
        />
      )}
      {dialog?.kind === "delete" && (
        <DeleteEventDialog
          event={dialog.event}
          novelId={novelId}
          openerId={dialog.openerId}
          onCancel={() => setDialog({ kind: "edit", event: dialog.event, openerId: dialog.openerId })}
          onDeleted={() => setDialog(null)}
        />
      )}
    </div>
  );
}
