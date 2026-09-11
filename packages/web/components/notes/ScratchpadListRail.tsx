"use client";

/**
 * ScratchpadListRail — the /scratchpad left rail (NOTES-001 §7): page
 * header, NoteFilterBar (T21/T21b), the honest search-mode badge, and the
 * note list with its loading / error+retry / empty states.
 *
 * Purely compositional (RULE-04 extraction from ScratchpadWorkspace so each
 * file stays under the 200-line limit): ALL data and state live in the
 * parent orchestrator; this module receives everything as props. The badge
 * text reflects the API-reported search mode (RULE-11 spirit) — never the
 * semantic toggle.
 */

import { StickyNote } from "lucide-react";
import { motion } from "motion/react";
import { useTranslations } from "next-intl";
import { bannerSlideVariants } from "@/lib/motion-variants";
import type { Note, NoteSearchMode } from "@/types";
import { NoteFilterBar, type NoteFilters, type ScopeOption } from "./NoteFilterBar";
import { NoteList } from "./NoteList";

export interface ScratchpadListRailProps {
  readonly filters: NoteFilters;
  readonly onFiltersChange: (next: NoteFilters) => void;
  readonly availableTags: readonly string[];
  readonly novels: readonly ScopeOption[];
  readonly series: readonly ScopeOption[];
  /** T21b gate — true while at least one displayed note is linked. */
  readonly hasLinks: boolean;
  readonly semanticMode: boolean;
  readonly onSemanticModeChange: (enabled: boolean) => void;
  readonly onSearchSubmit: () => void;
  /** API-reported mode of the active search; null hides the badge. */
  readonly searchMode: NoteSearchMode | null;
  readonly notes: readonly Note[];
  readonly selectedId: string | null;
  readonly onSelect: (noteId: string) => void;
  readonly listPending: boolean;
  readonly listError: boolean;
  readonly onRetryList: () => void;
}

export function ScratchpadListRail({
  filters,
  onFiltersChange,
  availableTags,
  novels,
  series,
  hasLinks,
  semanticMode,
  onSemanticModeChange,
  onSearchSubmit,
  searchMode,
  notes,
  selectedId,
  onSelect,
  listPending,
  listError,
  onRetryList,
}: ScratchpadListRailProps) {
  const t = useTranslations("notes");
  const tCommon = useTranslations("common");

  return (
    <div className="flex w-80 shrink-0 flex-col border-r border-border bg-background">
      <header className="border-b border-border p-4">
        <h1 className="flex items-center gap-2 text-lg font-medium tracking-tight text-foreground">
          <StickyNote className="size-5 text-primary" aria-hidden="true" />
          {t("page.title")}
        </h1>
        <p className="mt-0.5 text-xs font-normal text-muted-foreground">{t("page.subtitle")}</p>
      </header>
      <NoteFilterBar
        filters={filters}
        onFiltersChange={onFiltersChange}
        availableTags={availableTags}
        novels={novels}
        series={series}
        hasLinks={hasLinks}
        semanticMode={semanticMode}
        onSemanticModeChange={onSemanticModeChange}
        onSearchSubmit={onSearchSubmit}
      />
      {searchMode && (
        <motion.p
          variants={bannerSlideVariants}
          initial="hidden"
          animate="visible"
          data-testid="note-search-mode-badge"
          role="status"
          className="flex items-center gap-1.5 border-b border-border bg-muted/50 px-4 py-1 text-xs font-normal text-muted-foreground"
        >
          <span
            aria-hidden="true"
            className={`size-1.5 rounded-full ${
              searchMode === "semantic" ? "bg-primary" : "bg-muted-foreground"
            }`}
          />
          {searchMode === "semantic" ? t("search.semanticBadge") : t("search.lexicalBadge")}
        </motion.p>
      )}
      {listPending ? (
        <p className="motion-safe:animate-pulse p-8 text-center text-sm text-muted-foreground">
          {tCommon("loading")}
        </p>
      ) : listError ? (
        <div className="p-8 text-center text-sm text-muted-foreground">
          <p>{tCommon("error")}</p>
          <button
            type="button"
            data-testid="scratchpad-list-retry"
            className="mt-2 cursor-pointer rounded-md border border-border px-3 py-1.5 text-sm text-foreground transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            onClick={onRetryList}
          >
            {tCommon("retry")}
          </button>
        </div>
      ) : (
        <NoteList notes={notes} selectedId={selectedId} onSelect={onSelect} />
      )}
    </div>
  );
}
