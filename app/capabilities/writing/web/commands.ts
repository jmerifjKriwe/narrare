import { createElement, useState } from "react";

import { client } from "@shell/lib/api/client";
import type { Command } from "@shell/lib/commands";
import { queryClient, useNovelQuery } from "@shell/lib/query";

// The capability's palette rows: data only — no component imports, except
// inside `run`'s dynamic `import()`. The shell's generated registry
// (web/lib/generated/commands.ts) imports every commands module eagerly, so
// a component import here would drag this capability into the shell bundle;
// a dialog loads on first use instead, and the shell's modal slot mounts it
// under its own Suspense boundary. The type import is the one-way rule: the
// capability speaks the shell's command contract, the shell never imports
// this capability's code.
export const commands = [
  {
    id: "new-chapter",
    titleKey: "commands.newChapter",
    run: (ctx) => {
      if (ctx.novelId === null) return;
      const novelId = ctx.novelId;
      void (async () => {
        // An explicit empty title: the placeholder is a display concern, and
        // storing a title would freeze one locale's wording into the
        // database. The server treats an empty title exactly like an
        // omitted one.
        //
        // An accepted corner (spec §4): this POST precedes the workspace's
        // flush gate, so a navigation the gate goes on to ask about — and a
        // user who then declines — leaves the created, empty chapter in the
        // rail. Visible and honest, unlike a silent loss either way; WP6's
        // delete cleans it up. The rail's own button flushes first, and
        // that difference is accepted knowingly.
        const { data: chapter } = await client.POST(
          "/api/writing/novels/{novel_id}/chapters",
          { params: { path: { novel_id: novelId } }, body: { title: "" } },
        );
        if (!chapter) return;
        // The rail's list is the cache: the new row arrives through the
        // refetch this invalidation triggers, not through a hand-patched
        // array — every view of the key (the rail, the palette's next open)
        // reads the same answer. Awaited, so the param is written only once
        // the list that holds the row has landed and no dead-param cleanup
        // can mistake the new address for a dead one.
        await queryClient.invalidateQueries({ queryKey: ["chapters", novelId] });
        // The bookshelf hero names the last-touched book, and its truth is
        // the novel row's updated_at — a chapter write is the most common
        // way that changes, so the shelf's ["novels"] cache must not
        // outlive this POST: staleTime would keep the old order alive for
        // half a minute. The ask rides alongside, not awaited — the
        // selection waits only for the list it names. The same ask the
        // rail's own create makes.
        void queryClient.invalidateQueries({ queryKey: ["novels"] });
        void ctx.navigate({
          to: "/novels/$id",
          params: { id: novelId },
          search: (prev) => ({ ...prev, chapter: chapter.id }),
        });
      })();
    },
    enabled: (ctx) => ctx.novelId !== null,
  },
  {
    id: "export-novel",
    titleKey: "commands.exportNovel",
    run: (ctx) => {
      if (ctx.novelId === null) return;
      const novelId = ctx.novelId;
      ctx.openModal(async () => {
        const m = await import("./InterchangeDialogs");
        return {
          // The slot mounts a props-free component: this one reads the
          // book's row through Query (the workbench already asked for it)
          // and mounts the export dialog already open — the palette row was
          // the press. Closing it unmounts the overlay; the slot's next
          // open is a fresh mount.
          default: function ExportNovelFromPalette() {
            const novelQuery = useNovelQuery(novelId);
            const [open, setOpen] = useState(true);
            const novel = novelQuery.data;
            if (!novel) return null;
            return createElement(m.ExportNovelDialog, {
              novel,
              isOpen: open,
              onOpenChange: setOpen,
            });
          },
        };
      });
    },
    enabled: (ctx) => ctx.novelId !== null,
  },
] as const satisfies ReadonlyArray<Command>;
