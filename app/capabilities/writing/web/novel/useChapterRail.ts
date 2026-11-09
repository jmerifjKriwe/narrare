import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";

import type { Chapter } from "@shell/lib/api/client";
import { announce } from "@shell/lib/announce";
import { useTranslation } from "@shell/lib/i18n";
import { activeLocale } from "@shell/lib/locale";
import { queryClient, useReorderChapters } from "@shell/lib/query";
import { normalize } from "@shell/lib/search";

/**
 * The chapter rail's list state: the filter, the visible rows, the roving
 * walk, the reorder (keyboard and drag) and its failure. Takes the novel
 * id, the chapters and the open chapter id; the page renders the rows.
 */
export function useChapterRail(novelId: string, chapters: Chapter[], active: string | null) {
  const t = useTranslation();

  // The rail's reorder (WP6): Alt+↑/↓ on the focused row and a desktop
  // drag both end in one PUT of the whole rail. The arrangement is
  // written into the cache optimistically — the rail is the new order at
  // once, each row keeping its own updated_at (an arrangement is not a
  // write) — and any failure restores the list the ask replaced beside a
  // named notice. A 409 alone also refetches the key: the book's whole
  // changed in another tab, and the server's arrangement is the truth the
  // cache lacks. The shelf is asked for only on success, through the
  // mutation's own `onSuccess`.
  const reorder = useReorderChapters(novelId);
  const [orderFailed, setOrderFailed] = useState(false);
  // The tail of the reorder queue, the autosave's own pattern: never
  // rejects, so one failed ask cannot eat the moves queued behind it.
  // Serialization is the promise "survives a reload" keeps under key
  // repeat — two arrangements in flight at once can commit inverted, the
  // server holding the earlier permutation while the rail shows the last.
  const writes = useRef<Promise<unknown>>(Promise.resolve());
  // The rail's filter (Task 12): `null` is "no filter", the one state in
  // which a reorder is unambiguous — the guard Task 11 left behind. The
  // field's value arrives whole; a blank (trimmed-empty) answer is no
  // question at all and stores as `null`, so a cleared field and an
  // untouched one mean the same thing to every guard that reads this.
  const [railFilter, setRailFilter] = useState<string | null>(null);

  // The rail shows the question's answers: the rows whose rendered label —
  // the title, or the localized number an untitled row wears — contains the
  // needle, under the same normalization the palette searches by (one
  // definition, `lib/search.ts`). A filter is a view, never the book: the
  // cache and the editor keep every row, and the walk below indexes into
  // this list because this list is what rendered. The locale is a
  // dependency in its own right: `t` is a plain function whose identity
  // never changes, and the label it renders changes with the language — a
  // standing question is re-asked when the rows change their words, not
  // replayed against the previous language's answers.
  const locale = activeLocale();
  // biome-ignore lint/correctness/useExhaustiveDependencies: semantic key — `t` is a stable function whose output changes with the language, so `locale` stands in as the re-run key (see the comment above).
  const visibleChapters = useMemo(() => {
    if (railFilter === null) return chapters;
    const needle = normalize(railFilter.trim());
    return chapters.filter((chapter) =>
      normalize(
        chapter.title || t("chapters.defaultTitle", { n: chapter.position + 1 }),
      ).includes(needle),
    );
  }, [chapters, railFilter, locale]);

  // The open chapter's slot in that visible list: -1 when no chapter is
  // open, or when the filter hides the one that is — either way the rail's
  // first visible row takes the tab stop, so the list is never unreachable
  // by keyboard while a filter stands.
  const activeVisibleIndex = visibleChapters.findIndex((chapter) => chapter.id === active);

  // The filter dies where the book it filtered ends. Another book's rows —
  // the palette's jump keeps this page mounted, and one book's question
  // must not hide the next book's chapters — and a book whose length
  // changed, which is every create (the rail's own button clears above;
  // the palette's command lands here, through its invalidation) and every
  // delete: both end in a chapter the rail must show, and the row the
  // address names is never hidden by a stale question.
  const filteredBook = useRef(novelId);
  const bookLength = useRef(chapters.length);
  useEffect(() => {
    if (novelId === filteredBook.current && chapters.length === bookLength.current) return;
    filteredBook.current = novelId;
    bookLength.current = chapters.length;
    // The walk ends with the question: whatever row it stood on belongs to
    // a list that no longer exists, and a stale index would leave the
    // shortened rail without a tab stop.
    setWalkedIndex(null);
    setRailFilter(null);
  }, [novelId, chapters.length]);

  // The rail's roving walk (F20): the current row is the one tab stop, and
  // Up/Down move the focus along the rows. The walk moves focus only — the
  // chapter changes when a row is activated, never when it is walked past —
  // but the tab stop follows the focus while the walk lasts (APG): walk
  // away and one Tab returns to the row the user was on, not the row they
  // had selected. Activating a row hands the tab stop back to the selection.
  const railListRef = useRef<HTMLUListElement | null>(null);
  const [walkedIndex, setWalkedIndex] = useState<number | null>(null);
  const walkRail = useCallback((event: ReactKeyboardEvent, index: number) => {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    event.preventDefault();
    const rows = railListRef.current?.querySelectorAll<HTMLButtonElement>("button");
    if (!rows) return;
    const next = event.key === "ArrowDown" ? index + 1 : index - 1;
    if (next < 0 || next >= rows.length) return;
    setWalkedIndex(next);
    rows[next]?.focus();
  }, []);

  /** Move one chapter one step: the keyboard's Alt+↑/↓ path, and the
   *  address Task 10's menu items call. The ends are no-ops — nothing
   *  moves, nothing is asked. */
  async function move(chapterId: string, delta: -1 | 1): Promise<void> {
    if (railFilter !== null) return;
    const rows = queryClient.getQueryData<Array<Chapter>>(["chapters", novelId]);
    if (!rows) return;
    const from = rows.findIndex((chapter) => chapter.id === chapterId);
    const to = from + delta;
    if (from < 0 || to < 0 || to >= rows.length) return;
    await moveTo(chapterId, to);
  }

  /** Move one chapter to an index: the drag path's landing, and move's
   *  engine. Both reads are the cache's, not the render's list — two
   *  moves before a re-render must not compute the second from the
   *  first's before — and the first read doubles as the snapshot a
   *  failure restores. */
  async function moveTo(chapterId: string, index: number): Promise<void> {
    if (railFilter !== null) return;
    const previous = queryClient.getQueryData<Array<Chapter>>(["chapters", novelId]);
    if (!previous) return;
    const from = previous.findIndex((chapter) => chapter.id === chapterId);
    if (from < 0 || from === index || index < 0 || index >= previous.length) return;
    const moved = previous[from];
    const without = previous.filter((chapter) => chapter.id !== chapterId);
    const next = [...without.slice(0, index), moved, ...without.slice(index)].map(
      (chapter, position) => ({ ...chapter, position }),
    );
    // A plain list tells AT nothing about a reordering: every move is
    // announced with the row's name — the one it wore as the move began,
    // the name the keystroke or the grab was aimed at — and the position
    // it holds now, out of the book's total.
    announce(
      t("chapters.moved", {
        title: moved.title || t("chapters.defaultTitle", { n: moved.position + 1 }),
        n: index + 1,
        m: next.length,
      }),
    );
    // The optimistic write: the rail and the cache agree at once, the
    // numbering rewritten to the arrangement the rows now stand in.
    // `setQueryData` runs the value through structural sharing and
    // answers with the object the cache actually stored — never the
    // `next` we passed — so the identity guard below compares against
    // the RETURN: the one reference a later read can still find there.
    const written = queryClient.setQueryData<Array<Chapter>>(
      ["chapters", novelId],
      next,
    );
    setOrderFailed(false);
    // The ask waits its turn: one arrangement on the wire at a time,
    // chained on the queue's tail. This move's promise (`ask`) can
    // reject into its own handler; the tail cannot, or a later keystroke
    // would queue behind a failure and never fly.
    const ask = writes.current.then(() =>
      reorder.mutateAsync(next.map((chapter) => chapter.id)),
    );
    writes.current = ask.catch(() => undefined);
    try {
      await ask;
    } catch (failure) {
      // Restore only what is still this move's to restore: the cache
      // must hold the very object this move's write stored, or a later
      // move's optimistic order — newer than this snapshot — would be
      // clobbered by an earlier failure. The notice still names the
      // refusal either way. A 409 asks the key to refetch, the server's
      // order arriving through the same door every list does; a
      // transport failure asks for nothing — the service is not
      // answering, and a second ask would only name a refresh failure
      // beside work that stays.
      if (queryClient.getQueryData<Array<Chapter>>(["chapters", novelId]) === written) {
        queryClient.setQueryData<Array<Chapter>>(["chapters", novelId], previous);
      }
      setOrderFailed(true);
      if ((failure as { status?: number }).status === 409) {
        void queryClient.invalidateQueries({ queryKey: ["chapters", novelId] });
      }
    }
  }

  // The desktop drag's state. The dragged id rides component state, not
  // `dataTransfer`: the DOM test drives the events alone, and no drop
  // reads data some other surface would have to write. `dropIndex` is
  // the marker's truth — which slot the drop would land at — read by the
  // render, not by the drop itself (the slot's own handler knows its
  // index; the state would be one event behind it).
  const dragId = useRef<string | null>(null);
  const [dropIndex, setDropIndex] = useState<number | null>(null);

  return {
    visibleChapters,
    activeVisibleIndex,
    railListRef,
    walkedIndex,
    setWalkedIndex,
    walkRail,
    railFilter,
    setRailFilter,
    orderFailed,
    move,
    moveTo,
    dragId,
    dropIndex,
    setDropIndex,
  };
}
