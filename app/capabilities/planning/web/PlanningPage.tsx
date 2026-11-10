import { Link, useSearch } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";

import { Button } from "@shell/ui/Button";
import { Dialog } from "@shell/ui/Dialog";
import { Field, Input, Select, Textarea } from "@shell/ui/field";
import { client, type Chapter } from "@shell/lib/api/client";
import type { components } from "@shell/lib/api/schema";
import { useTranslation } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import { useChaptersQuery, useNovelsQuery } from "@shell/lib/query";
import { Notice } from "@shell/ui/Notice";
import { Row } from "@shell/ui/Row";

type TimelineEvent = components["schemas"]["TimelineEventRead"];

/** The canvas never renders more rows than this: a longer timeline states
 *  its size beside the slice it shows, and the rest stays one query away. */
export const EVENT_LIMIT = 200;

type View = "chrono" | "chapters";

/**
 * The seam the timeline reads through: the page renders only what this
 * returns, and the return names the one honest split — an answer that is
 * not "ok" is `failed`, never an empty list, because "no events" is a
 * fact only a reachable service can claim (the documents read's F14
 * precedent). An ok answer with no data is honestly empty; with data,
 * the rows pass through untouched. Exported for the unit test.
 */
export function readEvents(result: {
  data?: TimelineEvent[];
  response: { ok: boolean };
}): { kind: "ok"; events: TimelineEvent[] } | { kind: "failed" } {
  if (!result.response.ok) return { kind: "failed" };
  return { kind: "ok", events: result.data ?? [] };
}

/** The server's refusal, when it named one — the PlanningErrorRead detail. */
function refusalDetail(error: unknown): string | null {
  const detail = (error as { detail?: unknown } | null | undefined)?.detail;
  return typeof detail === "string" && detail !== "" ? detail : null;
}

/** A position the form can carry: a number, or the empty string for none. */
function parsePosition(raw: string): number | null {
  const trimmed = raw.trim();
  if (trimmed === "") return null;
  if (!/^-?\d+$/.test(trimmed)) return null;
  return Number(trimmed);
}

/**
 * The Planen landing canvas: the novel's hand-placed story events as one
 * readable page, in the writer's own order or grouped under the chapters
 * they belong to. The novel arrives as the `?novel=` search param (the
 * graph's sibling: tolerant in, absent means the picker); a param naming
 * nothing the read returns degrades to the empty state, never an error.
 */
export function PlanningPage() {
  const t = useTranslation();
  // The tab's name: this page is "Planung" until it goes.
  usePageTitle(t("planning.heading"));
  const { novel: novelId } = useSearch({ from: "/planning" });
  // A param naming no novel is no novel: the empty string is the absent
  // state, not a novel called "".
  const current = novelId === "" ? undefined : novelId;

  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-10">
      <h1 className="text-title font-semibold tracking-tight">{t("planning.heading")}</h1>
      {current === undefined ? <NovelPicker /> : <NovelTimeline novelId={current} />}
    </div>
  );
}

/** No novel named: the novels to plan, one link each. */
function NovelPicker() {
  const t = useTranslation();
  const novels = useNovelsQuery();

  if (novels.isPending) {
    return (
      <Notice tone="quiet" live="status" className="mt-6">
        {t("planning.timelineLoading")}
      </Notice>
    );
  }
  if (novels.isError) {
    return (
      <Notice
        tone="danger"
        live="alert"
        className="mt-6"
        action={
          <Button variant="secondary" onClick={() => void novels.refetch()}>
            {t("planning.retry")}
          </Button>
        }
      >
        {t("planning.timelineLoadFailed")}
      </Notice>
    );
  }
  const rows = novels.data ?? [];
  if (rows.length === 0) {
    return (
      <Notice
        tone="quiet"
        className="mt-6"
        action={
          <Link
            to="/"
            className="shrink-0 underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
          >
            {t("nav.back")}
          </Link>
        }
      >
        {t("planning.noNovels")}
      </Notice>
    );
  }
  return (
    <nav aria-label={t("planning.pickNovel")} className="mt-6 flex flex-col gap-2">
      {rows.map((novel) => (
        <Link
          key={novel.id}
          to="/planning"
          search={{ novel: novel.id }}
          className="underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
        >
          {novel.title}
        </Link>
      ))}
    </nav>
  );
}

/** The named novel's canvas: its events in order, or under their chapters. */
function NovelTimeline({ novelId }: { novelId: string }) {
  const t = useTranslation();
  const [view, setView] = useState<View>("chrono");
  const eventsQuery = useQuery({
    queryKey: ["planning", "events", novelId],
    queryFn: async () => {
      const answer = await client.GET("/api/planning/novels/{novel_id}/timeline-events", {
        params: { path: { novel_id: novelId } },
      });
      const read = readEvents(answer);
      if (read.kind === "failed") {
        throw new Error(`events unavailable: ${answer.response.status}`);
      }
      return read.events;
    },
  });
  // The chapters name the by-chapter view's groups and fill the chapter
  // select of the add/edit dialogs — one cached list, the workbench's own.
  const chapters = useChaptersQuery(novelId);

  async function reload() {
    await eventsQuery.refetch();
  }

  if (eventsQuery.isPending || chapters.isPending) {
    return (
      <Notice tone="quiet" live="status" className="mt-6">
        {t("planning.timelineLoading")}
      </Notice>
    );
  }
  if (eventsQuery.isError || chapters.isError) {
    return (
      <Notice
        tone="danger"
        live="alert"
        className="mt-6"
        action={
          <Button
            variant="secondary"
            onClick={() => void Promise.allSettled([eventsQuery.refetch(), chapters.refetch()])}
          >
            {t("planning.retry")}
          </Button>
        }
      >
        {t("planning.timelineLoadFailed")}
      </Notice>
    );
  }
  const events = eventsQuery.data ?? [];
  const chapterRows = chapters.data ?? [];
  if (events.length === 0) {
    return (
      <>
        <p className="mt-2 text-body text-muted">
          <Link
            to="/planning"
            className="underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
          >
            {t("planning.changeNovel")}
          </Link>
        </p>
        {/* The honest empty: no events is a fact the service confirmed,
            and the next step stands beside it as the page's one primary. */}
        <Notice tone="quiet" className="mt-6">
          {t("planning.timelineEmpty")}
        </Notice>
        <div className="mt-3">
          <Dialog
            title={t("planning.dialogAddEvent")}
            triggerLabel={t("planning.addEvent")}
            triggerVariant="primary"
          >
            {(close) => (
              <EventForm novelId={novelId} chapters={chapterRows} close={close} onSaved={reload} />
            )}
          </Dialog>
        </div>
      </>
    );
  }
  const total = events.length;
  const shown = events.slice(0, EVENT_LIMIT);
  return (
    <>
      <p className="mt-2 text-body text-muted">
        <Link
          to="/planning"
          className="underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
        >
          {t("planning.changeNovel")}
        </Link>
      </p>
      <div className="mt-6 flex flex-wrap items-center gap-2">
        <Button
          variant="secondary"
          aria-pressed={view === "chrono"}
          className={view === "chrono" ? "font-semibold" : undefined}
          onClick={() => setView("chrono")}
        >
          {t("planning.viewChrono")}
        </Button>
        <Button
          variant="secondary"
          aria-pressed={view === "chapters"}
          className={view === "chapters" ? "font-semibold" : undefined}
          onClick={() => setView("chapters")}
        >
          {t("planning.viewByChapter")}
        </Button>
        <span className="ml-auto">
          <Dialog
            title={t("planning.dialogAddEvent")}
            triggerLabel={t("planning.addEvent")}
            triggerVariant="primary"
          >
            {(close) => (
              <EventForm novelId={novelId} chapters={chapterRows} close={close} onSaved={reload} />
            )}
          </Dialog>
        </span>
      </div>
      {view === "chrono" ? (
        <Chronological events={shown} chapters={chapterRows} novelId={novelId} onChanged={reload} />
      ) : (
        <ByChapter events={shown} chapters={chapterRows} novelId={novelId} onChanged={reload} />
      )}
      {total > EVENT_LIMIT ? (
        <Notice tone="info" className="mt-3">
          {t("planning.showingLimited", { shown: shown.length, total })}
        </Notice>
      ) : null}
    </>
  );
}

/** The chapter's name for one event, or nothing when it has none to show. */
function chapterName(chapters: Chapter[], chapterId: string | null): string | null {
  if (chapterId === null) return null;
  const chapter = chapters.find((candidate) => candidate.id === chapterId);
  if (chapter === undefined) return null;
  return chapter.title.trim() === "" ? null : chapter.title;
}

/** The events in the server's own order: position first, dateless rows last. */
function Chronological({
  events,
  chapters,
  novelId,
  onChanged,
}: {
  events: TimelineEvent[];
  chapters: Chapter[];
  novelId: string;
  onChanged: () => Promise<void>;
}) {
  return (
    <ul className="mt-4 flex flex-col">
      {events.map((event) => (
        <li key={event.id}>
          <EventRow
            event={event}
            chapterLabel={chapterName(chapters, event.chapter_id)}
            novelId={novelId}
            chapters={chapters}
            onChanged={onChanged}
          />
        </li>
      ))}
    </ul>
  );
}

/** The same events under their chapters: position order, loose rows last. */
function ByChapter({
  events,
  chapters,
  novelId,
  onChanged,
}: {
  events: TimelineEvent[];
  chapters: Chapter[];
  novelId: string;
  onChanged: () => Promise<void>;
}) {
  const t = useTranslation();
  const headingId = useId();
  const looseId = `${headingId}-loose`;
  const byChapterId = new Map(chapters.map((chapter) => [chapter.id, chapter]));
  const loose = events.filter((event) => event.chapter_id === null || !byChapterId.has(event.chapter_id));

  return (
    <div className="mt-4 flex flex-col gap-6">
      {chapters.map((chapter, index) => {
        const rows = events.filter((event) => event.chapter_id === chapter.id);
        if (rows.length === 0) return null;
        const name = chapter.title.trim() === "" ? t("planning.untitledChapter") : chapter.title;
        return (
          <section key={chapter.id} aria-labelledby={`${headingId}-${index}`}>
            <h2 id={`${headingId}-${index}`} className="text-label font-semibold text-muted">
              {name}
            </h2>
            <ul className="mt-1 flex flex-col">
              {rows.map((event) => (
                <li key={event.id}>
                  <EventRow
                    event={event}
                    chapterLabel={null}
                    novelId={novelId}
                    chapters={chapters}
                    onChanged={onChanged}
                  />
                </li>
              ))}
            </ul>
          </section>
        );
      })}
      {loose.length === 0 ? null : (
        <section aria-labelledby={looseId}>
          <h2 id={looseId} className="text-label font-semibold text-muted">
            {t("planning.noChapter")}
          </h2>
          <ul className="mt-1 flex flex-col">
            {loose.map((event) => (
              <li key={event.id}>
                <EventRow
                  event={event}
                  chapterLabel={null}
                  novelId={novelId}
                  chapters={chapters}
                  onChanged={onChanged}
                />
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

/** One event: its position, its words, and what it belongs to. */
function EventRow({
  event,
  chapterLabel,
  novelId,
  chapters,
  onChanged,
}: {
  event: TimelineEvent;
  /** The chapter's name in the flat view; the grouped view's section says it. */
  chapterLabel: string | null;
  novelId: string;
  chapters: Chapter[];
  onChanged: () => Promise<void>;
}) {
  const t = useTranslation();
  const position = event.position === null ? t("planning.unordered") : `#${event.position}`;

  return (
    <Row
      as="div"
      role="group"
      aria-label={event.title}
      flush
      className="h-auto flex-col items-stretch gap-1 py-2"
    >
      <div className="flex flex-wrap items-baseline gap-x-2">
        <span className="shrink-0 text-label text-muted">{position}</span>
        <span className="min-w-0 flex-1 text-body font-semibold">{event.title}</span>
        {event.date_label.trim() !== "" ? (
          <span className="shrink-0 text-label text-muted">{event.date_label}</span>
        ) : null}
      </div>
      {event.description.trim() !== "" ? (
        <p className="text-body text-muted group-hover:text-foreground">{event.description}</p>
      ) : null}
      {event.character_names.length > 0 ? (
        <p className="text-label text-muted">{event.character_names.join(", ")}</p>
      ) : null}
      {chapterLabel !== null ? (
        <p className="text-label text-muted">{chapterLabel}</p>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <Dialog
          title={t("planning.editEvent")}
          triggerLabel={t("planning.edit")}
          triggerAriaLabel={t("planning.editFor", { title: event.title })}
        >
          {(close) => (
            <EventForm
              novelId={novelId}
              chapters={chapters}
              initial={event}
              close={close}
              onSaved={onChanged}
            />
          )}
        </Dialog>
        <Dialog
          title={t("planning.deleteTitle")}
          triggerLabel={t("planning.delete")}
          triggerAriaLabel={t("planning.deleteFor", { title: event.title })}
        >
          {(close) => (
            <DeleteForm novelId={novelId} event={event} close={close} onDeleted={onChanged} />
          )}
        </Dialog>
      </div>
    </Row>
  );
}

/** The add/edit form: the fields, the failure and the save live with one mounting. */
function EventForm({
  novelId,
  chapters,
  initial,
  close,
  onSaved,
}: {
  novelId: string;
  chapters: Chapter[];
  /** The edited event; absent is a creation. */
  initial?: TimelineEvent;
  close: () => void;
  onSaved: () => Promise<void>;
}) {
  const t = useTranslation();
  const [title, setTitle] = useState(initial?.title ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [dateLabel, setDateLabel] = useState(initial?.date_label ?? "");
  const [chapterId, setChapterId] = useState(initial?.chapter_id ?? "");
  const [position, setPosition] = useState(
    initial?.position === null || initial?.position === undefined ? "" : String(initial.position),
  );
  const [characters, setCharacters] = useState((initial?.character_names ?? []).join(", "));
  const [failed, setFailed] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function save(): Promise<void> {
    // A blank title is refused by the server (422); the dialog keeps the
    // typed work instead of asking for a refusal it can see coming.
    if (title.trim() === "" || busy) return;
    setBusy(true);
    setFailed(null);
    const body = {
      title: title.trim(),
      description,
      date_label: dateLabel,
      character_names: characters
        .split(",")
        .map((name) => name.trim())
        .filter((name) => name !== ""),
      chapter_id: chapterId === "" ? null : chapterId,
      position: parsePosition(position),
    };
    try {
      const answer =
        initial === undefined
          ? await client.POST("/api/planning/novels/{novel_id}/timeline-events", {
              params: { path: { novel_id: novelId } },
              body,
            })
          : await client.PUT("/api/planning/novels/{novel_id}/timeline-events/{event_id}", {
              params: { path: { novel_id: novelId, event_id: initial.id } },
              body,
            });
      if (!answer.response.ok) {
        setFailed(refusalDetail(answer.error) ?? t("planning.saveOffline"));
        return;
      }
    } catch {
      // A service that does not answer is a refused write, not silence:
      // the dialog keeps the typed work and names the refusal where the
      // retry — the same save — sits.
      setFailed(t("planning.saveOffline"));
      return;
    } finally {
      setBusy(false);
    }
    // The write moved the server's truth: the list re-asks before the
    // dialog leaves, so no stale row stands in for the saved one.
    await onSaved();
    close();
  }

  return (
    <form
      onSubmit={(form) => {
        form.preventDefault();
        void save();
      }}
      className="mt-4 flex flex-col gap-3"
    >
      <Field label={t("planning.titleLabel")}>
        <Input value={title} maxLength={500} onChange={(form) => setTitle(form.target.value)} />
      </Field>
      <Field label={t("planning.descriptionLabel")}>
        <Textarea value={description} onChange={(form) => setDescription(form.target.value)} />
      </Field>
      <Field label={t("planning.dateLabelLabel")}>
        <Input
          value={dateLabel}
          maxLength={200}
          onChange={(form) => setDateLabel(form.target.value)}
        />
      </Field>
      <Field label={t("planning.chapterLabel")}>
        <Select value={chapterId} onChange={(form) => setChapterId(form.target.value)}>
          <option value="">{t("planning.noChapter")}</option>
          {chapters.map((chapter) => (
            <option key={chapter.id} value={chapter.id}>
              {chapter.title.trim() === "" ? t("planning.untitledChapter") : chapter.title}
            </option>
          ))}
        </Select>
      </Field>
      <Field label={t("planning.positionLabel")}>
        <Input
          type="number"
          value={position}
          onChange={(form) => setPosition(form.target.value)}
        />
      </Field>
      <Field label={t("planning.charactersLabel")}>
        <Input value={characters} onChange={(form) => setCharacters(form.target.value)} />
      </Field>
      {failed !== null ? (
        <Notice
          tone="danger"
          live="alert"
          action={
            <Button variant="secondary" onClick={() => void save()}>
              {t("planning.retry")}
            </Button>
          }
        >
          {t("planning.saveFailed", { detail: failed })}
        </Notice>
      ) : null}
      <div className="mt-2 flex justify-end gap-3">
        <Button onClick={close}>{t("planning.cancel")}</Button>
        <Button variant="primary" type="submit" disabled={busy}>
          {initial === undefined ? t("planning.addEvent") : t("planning.saveEvent")}
        </Button>
      </div>
    </form>
  );
}

/**
 * Delete an event: the confirm names the event, a refusal stays open and
 * is named where the retry — the same confirm — sits; the 204 closes the
 * dialog after the list has re-read.
 */
function DeleteForm({
  novelId,
  event,
  close,
  onDeleted,
}: {
  novelId: string;
  event: TimelineEvent;
  close: () => void;
  onDeleted: () => Promise<void>;
}) {
  const t = useTranslation();
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);

  async function confirm(): Promise<void> {
    if (busy) return;
    setBusy(true);
    setFailed(null);
    try {
      const { error, response } = await client.DELETE(
        "/api/planning/novels/{novel_id}/timeline-events/{event_id}",
        { params: { path: { novel_id: novelId, event_id: event.id } } },
      );
      if (!response.ok) {
        setFailed(refusalDetail(error) ?? t("planning.saveOffline"));
        return;
      }
    } catch {
      setFailed(t("planning.saveOffline"));
      return;
    } finally {
      setBusy(false);
    }
    await onDeleted();
    close();
  }

  return (
    <div className="mt-4 flex flex-col gap-3">
      <p className="text-body text-muted">{t("planning.deleteBody", { title: event.title })}</p>
      {failed !== null ? (
        <Notice
          tone="danger"
          live="alert"
          action={
            <Button variant="secondary" onClick={() => void confirm()}>
              {t("planning.retry")}
            </Button>
          }
        >
          {t("planning.saveFailed", { detail: failed })}
        </Notice>
      ) : null}
      <div className="mt-2 flex justify-end gap-3">
        <Button onClick={close}>{t("planning.cancel")}</Button>
        <Button variant="primary" disabled={busy} onClick={() => void confirm()}>
          {t("planning.delete")}
        </Button>
      </div>
    </div>
  );
}
