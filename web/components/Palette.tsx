import { ModalOverlay, Modal, Dialog as RacDialog, TextField as RacTextField, Input } from "react-aria-components";
import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ComponentType, KeyboardEvent as ReactKeyboardEvent, ReactNode } from "react";

import { useNavigate, useParams } from "@tanstack/react-router";

import { matchesAllLocales, matchesAnyText, type Command, type CommandContext } from "../lib/commands";
import { nav } from "../lib/generated/capabilities";
import { commands } from "../lib/generated/commands";
import { docks } from "../lib/generated/docks";
import { useTranslation } from "../lib/i18n";
import { useChaptersQuery, useEntitiesQuery, useNovelsQuery } from "../lib/query";

/** The loader a command hands to the modal slot, exactly as the contract has it. */
type ModalLoad = () => Promise<{ default: ComponentType }>;

/** The registries' paths, as the generated tables hold them. */
type DockPath = (typeof docks)[number]["path"];
type PagePath = (typeof nav)[number]["path"];

const ROW_BUTTON =
  "rounded-md px-3 py-2 text-left text-sm focus:bg-panel focus:outline-none";
const GROUP_LABEL = "px-3 pb-1 pt-2 text-xs font-medium text-muted";

/**
 * One row of the palette: a button the keyboard walks into (the search
 * field's ArrowDown enters the list, the arrows walk it, ArrowUp on the
 * first row returns to the field) and Enter or a click activates.
 */
function Row({
  onActivate,
  onRowKeyDown,
  children,
}: {
  onActivate: () => void;
  onRowKeyDown: (event: ReactKeyboardEvent) => void;
  children: ReactNode;
}) {
  return (
    <button type="button" data-palette-row onClick={onActivate} onKeyDown={onRowKeyDown} className={ROW_BUTTON}>
      {children}
    </button>
  );
}

/**
 * One labelled group. The count is reported up so the palette can name the
 * empty truth once — the group itself just steps aside when its filtered
 * rows come out empty.
 */
function Group({
  label,
  count,
  onCount,
  children,
}: {
  label: string;
  count: number;
  onCount: (count: number) => void;
  children: ReactNode;
}) {
  useEffect(() => {
    onCount(count);
  }, [count, onCount]);
  if (count === 0) return null;
  return (
    <div role="group" aria-label={label}>
      <p className={GROUP_LABEL}>{label}</p>
      <div className="flex flex-col">{children}</div>
    </div>
  );
}

/**
 * The chapters of the current book. The list is the workspace's own cached
 * answer — the palette asks nothing the workbench would not ask — and a
 * result is a deep link: `?chapter=` is the selection's address, the same
 * one the rail writes.
 */
function ChaptersGroup({
  novelId,
  query,
  onCount,
  onRowKeyDown,
  onJump,
}: {
  novelId: string;
  query: string;
  onCount: (count: number) => void;
  onRowKeyDown: (event: ReactKeyboardEvent) => void;
  onJump: (chapterId: string) => void;
}) {
  const t = useTranslation();
  const chapters = useChaptersQuery(novelId).data;
  const rows = (chapters ?? []).filter((chapter) =>
    matchesAnyText(query, [
      chapter.title,
      t("chapters.defaultTitle", { n: chapter.position + 1 }),
    ]),
  );
  return (
    <Group label={t("palette.chapters")} count={rows.length} onCount={onCount}>
      {rows.map((chapter) => (
        <Row key={chapter.id} onRowKeyDown={onRowKeyDown} onActivate={() => onJump(chapter.id)}>
          {chapter.title || t("chapters.defaultTitle", { n: chapter.position + 1 })}
        </Row>
      ))}
    </Group>
  );
}

/**
 * The current book's entities, matched over name, aliases and tags — the
 * words the card itself knows by. A result opens the Wissen dock with the
 * entity selected: `?entity=`, the chapter param's sibling.
 */
function EntitiesGroup({
  novelId,
  query,
  onCount,
  onRowKeyDown,
  onJump,
}: {
  novelId: string;
  query: string;
  onCount: (count: number) => void;
  onRowKeyDown: (event: ReactKeyboardEvent) => void;
  onJump: (entityId: string) => void;
}) {
  const t = useTranslation();
  const entities = useEntitiesQuery(novelId).data;
  const rows = (entities ?? []).filter((entity) =>
    matchesAnyText(query, [entity.name, ...entity.aliases, ...entity.tags]),
  );
  return (
    <Group label={t("palette.entities")} count={rows.length} onCount={onCount}>
      {rows.map((entity) => (
        <Row key={entity.id} onRowKeyDown={onRowKeyDown} onActivate={() => onJump(entity.id)}>
          {entity.name}
        </Row>
      ))}
    </Group>
  );
}

/**
 * The shelf, when no book is open: Novels replaces Chapters and Entities,
 * so ⌘K is the app-wide path and the mouse is never required anywhere. A
 * result is an ordinary jump to the book — which then names its own
 * last-touched chapter, nothing carried over from the old one.
 */
function NovelsGroup({
  query,
  onCount,
  onRowKeyDown,
  onJump,
}: {
  query: string;
  onCount: (count: number) => void;
  onRowKeyDown: (event: ReactKeyboardEvent) => void;
  onJump: (novelId: string) => void;
}) {
  const t = useTranslation();
  const novels = useNovelsQuery().data;
  const rows = (novels ?? []).filter((novel) => matchesAnyText(query, [novel.title]));
  return (
    <Group label={t("palette.novels")} count={rows.length} onCount={onCount}>
      {rows.map((novel) => (
        <Row key={novel.id} onRowKeyDown={onRowKeyDown} onActivate={() => onJump(novel.id)}>
          {novel.title}
        </Row>
      ))}
    </Group>
  );
}

/**
 * Docks and pages, straight from the generated registries — the palette
 * holds no hand-written list of its own. The docks live at a novel, so
 * without one only the app-wide pages show. Matched by their catalog
 * renderings, like the commands.
 */
function PagesGroup({
  novelId,
  query,
  onCount,
  onRowKeyDown,
  onOpen,
}: {
  novelId: string | null;
  query: string;
  onCount: (count: number) => void;
  onRowKeyDown: (event: ReactKeyboardEvent) => void;
  onOpen: (path: DockPath | PagePath, novelScoped: boolean) => void;
}) {
  const t = useTranslation();
  const pages: Array<{
    key: string;
    path: DockPath | PagePath;
    titleKey: (typeof docks)[number]["titleKey"] | (typeof nav)[number]["titleKey"];
    novelScoped: boolean;
  }> = [
    ...docks.map((dock) => ({
      key: `dock:${dock.id}`,
      path: dock.path,
      titleKey: dock.titleKey,
      novelScoped: true,
    })),
    ...nav.map((entry) => ({
      key: `page:${entry.id}`,
      path: entry.path,
      titleKey: entry.titleKey,
      novelScoped: false,
    })),
  ];
  const open = pages.filter((page) => (page.novelScoped ? novelId !== null : true));
  const rows = open.filter((page) => matchesAllLocales(page.titleKey, query));
  return (
    <Group label={t("palette.pages")} count={rows.length} onCount={onCount}>
      {rows.map((page) => (
        <Row
          key={page.key}
          onRowKeyDown={onRowKeyDown}
          onActivate={() => onOpen(page.path, page.novelScoped)}
        >
          {t(page.titleKey)}
        </Row>
      ))}
    </Group>
  );
}

/**
 * The capabilities' own rows, read from the generated aggregation — the
 * palette owns no command of its own; it renders what the capabilities
 * contribute and runs each with the context the shell holds.
 */
function CommandsGroup({
  query,
  ctx,
  onCount,
  onRowKeyDown,
  onClose,
}: {
  query: string;
  ctx: CommandContext;
  onCount: (count: number) => void;
  onRowKeyDown: (event: ReactKeyboardEvent) => void;
  onClose: () => void;
}) {
  const t = useTranslation();
  // The aggregation's literal union hides `enabled` on the rows that have
  // none; read through the contract, like the tests do.
  const all: ReadonlyArray<Command> = commands;
  const rows = all.filter(
    (command) => command.enabled?.(ctx) !== false && matchesAllLocales(command.titleKey, query),
  );
  return (
    <Group label={t("palette.commands")} count={rows.length} onCount={onCount}>
      {rows.map((command) => (
        <Row
          key={command.id}
          onRowKeyDown={onRowKeyDown}
          onActivate={() => {
            command.run(ctx);
            onClose();
          }}
        >
          {t(command.titleKey)}
        </Row>
      ))}
    </Group>
  );
}

/**
 * The app's keyboard surface. Mounted once by the shell, it answers on
 * every route: ⌘K opens it (the listener lives beside the mount, in the
 * shell root), Esc closes it, and the focus returns to whatever held it —
 * captured at open, returned at close (the palette has no trigger for
 * React Aria to restore to; the key is its opener). Its groups fill from
 * the context the current route carries; nothing the palette shows or does
 * is persisted. A command's dialog loads through the modal slot below —
 * the one Suspense boundary whose chunk arrives on first use, not on page
 * load.
 */
export function Palette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const t = useTranslation();
  const navigate = useNavigate();
  // The novel the active route carries, read tolerantly: outside a
  // workspace this is undefined, and Novels takes the first two groups'
  // places.
  const workspace = useParams({ from: "/novels/$id", shouldThrow: false });
  const novelId = workspace?.id ?? null;

  // The groups report their filtered sizes; their sum decides the one
  // "nothing matches" line. Reporting settles after the render that shows
  // the rows, so a just-opened palette cannot flash the empty truth.
  const [counts, setCounts] = useState<Record<string, number>>({});
  const report = useCallback((group: string, count: number) => {
    setCounts((previous) =>
      previous[group] === count ? previous : { ...previous, [group]: count },
    );
  }, []);

  // A fresh field on every open: the search is this open's question, never
  // a previous one's leftover.
  const [query, setQuery] = useState("");
  // The opener's focus: captured when the palette opens (the ⌘K press moves
  // no focus, so whatever held it is still held), returned when it closes.
  // React Aria's focus scope restores for its triggers; the palette has no
  // trigger — the key is its opener — so the return is the palette's own.
  const opener = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (open) {
      opener.current = document.activeElement as HTMLElement | null;
      setQuery("");
      setCounts({});
    } else {
      opener.current?.focus();
      opener.current = null;
    }
  }, [open]);
  const shown = Object.values(counts).reduce((sum, count) => sum + count, 0);
  const nothing = query.trim() !== "" && shown === 0;

  // The modal slot the commands share. The palette steps aside when one
  // runs; the slot keeps a fresh key per open, so the same dialog can be
  // opened, closed and opened again — a remount each time, not a reuse.
  const [modal, setModal] = useState<{ load: ModalLoad; key: number } | null>(null);
  const nextModalKey = useRef(0);
  const openModal: CommandContext["openModal"] = useCallback(
    (load) => {
      onOpenChange(false);
      nextModalKey.current += 1;
      setModal({ load, key: nextModalKey.current });
    },
    [onOpenChange],
  );
  const ModalComponent = useMemo(
    () => (modal === null ? null : lazy(modal.load)),
    [modal],
  );

  const ctx: CommandContext = { navigate, novelId, openModal };

  const jumpToChapter = useCallback(
    (chapterId: string) => {
      if (novelId === null) return;
      void navigate({
        to: "/novels/$id",
        params: { id: novelId },
        search: (prev) => ({ ...prev, chapter: chapterId }),
      });
      onOpenChange(false);
    },
    [navigate, novelId, onOpenChange],
  );

  const jumpToEntity = useCallback(
    (entityId: string) => {
      if (novelId === null) return;
      void navigate({
        to: "/novels/$id/wissen",
        params: { id: novelId },
        search: (prev) => ({ ...prev, entity: entityId }),
      });
      onOpenChange(false);
    },
    [navigate, novelId, onOpenChange],
  );

  const jumpToNovel = useCallback(
    (id: string) => {
      void navigate({ to: "/novels/$id", params: { id } });
      onOpenChange(false);
    },
    [navigate, onOpenChange],
  );

  // A dock opens with the workspace's panel state carried along (`search:
  // true` keeps whatever ?rail/?focus say); an app page starts clean. Every
  // row steps the palette aside as it acts — the jump is the whole gesture.
  const openPage = useCallback(
    (path: DockPath | PagePath, novelScoped: boolean) => {
      if (novelScoped) {
        if (novelId === null) return;
        void navigate({ to: path, params: { id: novelId }, search: true });
      } else {
        void navigate({ to: path });
      }
      onOpenChange(false);
    },
    [navigate, novelId, onOpenChange],
  );

  // The list walk. The rows are plain buttons in DOM order; the search
  // field's ArrowDown enters at the top, the arrows step, and ArrowUp on
  // the first row hands the focus back to the field.
  const listRef = useRef<HTMLDivElement | null>(null);
  const searchRef = useRef<HTMLInputElement | null>(null);
  const paletteRows = () =>
    Array.from(listRef.current?.querySelectorAll<HTMLElement>("[data-palette-row]") ?? []);
  const onSearchKeyDown = (event: ReactKeyboardEvent) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      paletteRows()[0]?.focus();
    } else if (event.key === "Enter") {
      // Enter from the field runs the first visible row — the palette's
      // fastest path stays on the keyboard.
      const first = paletteRows()[0];
      if (first) {
        event.preventDefault();
        first.click();
      }
    }
  };
  const onRowKeyDown = (event: ReactKeyboardEvent) => {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    event.preventDefault();
    const all = paletteRows();
    const index = all.indexOf(event.currentTarget as HTMLElement);
    const next = event.key === "ArrowDown" ? index + 1 : index - 1;
    if (next < 0) searchRef.current?.focus();
    else all[Math.min(next, all.length - 1)]?.focus();
  };

  return (
    <>
      <ModalOverlay
        isOpen={open}
        isDismissable
        onOpenChange={(next) => {
          if (!next) onOpenChange(false);
        }}
        className="fixed inset-0 z-40 overflow-y-auto bg-scrim p-4"
      >
        <Modal className="mx-auto mt-[10vh] mb-8 w-full max-w-xl overflow-hidden rounded-lg border border-border bg-card shadow-overlay">
          <RacDialog aria-label={t("palette.title")} className="flex flex-col outline-none">
            <div className="border-b border-border">
              <RacTextField
                aria-label={t("palette.searchLabel")}
                value={query}
                onChange={setQuery}
                onKeyDown={onSearchKeyDown}
                className="block w-full"
              >
                <Input
                  ref={searchRef}
                  placeholder={t("palette.searchLabel")}
                  className="w-full bg-transparent px-4 py-3 text-base outline-none placeholder:text-muted"
                />
              </RacTextField>
            </div>
            <div ref={listRef} className="max-h-[50vh] overflow-y-auto p-2">
              {novelId !== null ? (
                <>
                  <ChaptersGroup
                    novelId={novelId}
                    query={query}
                    onCount={(count) => report("chapters", count)}
                    onRowKeyDown={onRowKeyDown}
                    onJump={jumpToChapter}
                  />
                  <EntitiesGroup
                    novelId={novelId}
                    query={query}
                    onCount={(count) => report("entities", count)}
                    onRowKeyDown={onRowKeyDown}
                    onJump={jumpToEntity}
                  />
                </>
              ) : (
                <NovelsGroup
                  query={query}
                  onCount={(count) => report("novels", count)}
                  onRowKeyDown={onRowKeyDown}
                  onJump={jumpToNovel}
                />
              )}
              <PagesGroup
                novelId={novelId}
                query={query}
                onCount={(count) => report("pages", count)}
                onRowKeyDown={onRowKeyDown}
                onOpen={openPage}
              />
              <CommandsGroup
                query={query}
                ctx={ctx}
                onCount={(count) => report("commands", count)}
                onRowKeyDown={onRowKeyDown}
                onClose={() => onOpenChange(false)}
              />
              {nothing ? (
                <p className="px-3 py-6 text-center text-sm text-muted">
                  {t("palette.noResults")}
                </p>
              ) : null}
            </div>
            {/* §11's row: the focus shortcuts are named here and nowhere
                else — the palette is the one place the keyboard's map lives. */}
            <p className="border-t border-border px-4 py-2 text-xs text-muted">
              {t("workspace.shortcutHints")}
            </p>
          </RacDialog>
        </Modal>
      </ModalOverlay>
      {ModalComponent !== null ? (
        <Suspense fallback={null}>
          <ModalComponent />
        </Suspense>
      ) : null}
    </>
  );
}
