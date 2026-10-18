"use client";

/**
 * KB Entry List — Column 2 of the 3-column KB browser.
 *
 * Shows search bar, "New Entry" button, and filtered entry cards.
 */

import { ChevronRight, Plus, Search, Sparkles } from "lucide-react";
import { motion } from "motion/react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { SearchInput } from "@/components/ui/search-input";
import type { KBEntityType, KBEntry } from "@/lib/api/kb";
import { useKBDebouncedSearch } from "@/lib/hooks/useKB";
import { listContainerVariants, listItemVariants } from "@/lib/motion-variants";
import { formatRelativeTime, STATUS_COLORS, TYPE_ICONS } from "./constants";

interface KBEntryListProps {
  novelId: string;
  entries: KBEntry[];
  isLoading: boolean;
  selectedEntryId: string | null;
  activeType: KBEntityType | null;
  onSelectEntry: (entryId: string) => void;
  onCreateNew: () => void;
  onCreateAssisted: () => void;
  searchQuery?: string;
  onSearchQueryChange?: (query: string) => void;
}

export function KBEntryList({
  novelId,
  entries,
  isLoading,
  selectedEntryId,
  activeType,
  onSelectEntry,
  onCreateNew,
  onCreateAssisted,
  searchQuery: initialSearchQuery = "",
  onSearchQueryChange,
}: KBEntryListProps) {
  const t = useTranslations("studio");
  const [searchQuery, setSearchQuery] = useState(initialSearchQuery);
  const { setQuery, data: searchResults, isLoading: isSearching } = useKBDebouncedSearch(novelId);

  useEffect(() => {
    setSearchQuery(initialSearchQuery);
    setQuery(initialSearchQuery);
  }, [initialSearchQuery, setQuery]);

  const displayEntries = searchQuery.length > 0 ? (searchResults?.items ?? []) : entries;
  const ActiveIcon = activeType ? TYPE_ICONS[activeType] : Search;

  function handleSearchChange(value: string) {
    setSearchQuery(value);
    setQuery(value);
    onSearchQueryChange?.(value);
  }

  return (
    <div className="w-full lg:w-64 border-r border-border bg-muted/30 flex flex-col">
      {/* Action buttons */}
      <div className="p-3 border-b border-border space-y-2">
        <button
          type="button"
          onClick={onCreateNew}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity text-sm shadow-sm"
        >
          <Plus className="w-4 h-4" />
          <span>{t("kb.newEntry")}</span>
        </button>
        <button
          type="button"
          onClick={onCreateAssisted}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 border border-purple-300 dark:border-purple-700 text-purple-600 dark:text-purple-400 rounded-md hover:bg-purple-50 dark:hover:bg-purple-950/20 transition-colors text-sm"
        >
          <Sparkles className="w-4 h-4" />
          <span>{t("kb.newWithAI")}</span>
        </button>
        <SearchInput
          label={t("kb.search")}
          placeholder={t("kb.search")}
          value={searchQuery}
          onValueChange={handleSearchChange}
          onClear={() => handleSearchChange("")}
          clearLabel={t("kb.clearSearch")}
          visibleLabel={false}
        />
      </div>

      {/* Entry list */}
      <div className="flex-1 overflow-y-auto p-2">
        {(isLoading || isSearching) && (
          <div className="text-center py-8 text-muted-foreground text-sm">{t("kb.search")}</div>
        )}

        {!isLoading && !isSearching && displayEntries.length === 0 && (
          <div className="text-center py-12 text-muted-foreground text-sm">
            <ActiveIcon className="w-8 h-8 mx-auto mb-2 opacity-20" />
            <p className="mb-1">{t("kb.noEntries")}</p>
            {/* Show the guided empty state only when the entire KB is empty
                (no type filter, no search query) so the hint stays truthful. */}
            {activeType === null && searchQuery === "" && (
              <>
                <p className="mb-4 max-w-xs mx-auto">{t("kb.emptyStateHint")}</p>
                <button
                  type="button"
                  onClick={onCreateNew}
                  className="inline-flex items-center gap-1 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity"
                >
                  <Plus className="w-4 h-4" />
                  {t("kb.emptyStateCta")}
                </button>
              </>
            )}
          </div>
        )}

        {!isLoading && !isSearching && displayEntries.length > 0 && (
          <motion.div
            variants={listContainerVariants}
            initial="hidden"
            animate="visible"
            className="space-y-0.5"
          >
            {displayEntries.map((entry) => (
              <motion.div key={entry.id} variants={listItemVariants}>
                <EntryCard
                  entry={entry}
                  isSelected={selectedEntryId === entry.id}
                  onClick={() => onSelectEntry(entry.id)}
                />
              </motion.div>
            ))}
          </motion.div>
        )}
      </div>
    </div>
  );
}

// --- Entry Card (Task 9.4) ---

interface EntryCardProps {
  entry: KBEntry;
  isSelected: boolean;
  onClick: () => void;
}

function EntryCard({ entry, isSelected, onClick }: EntryCardProps) {
  const t = useTranslations("studio");
  const Icon = TYPE_ICONS[entry.entity_type];
  const statusClass = STATUS_COLORS[entry.status] ?? STATUS_COLORS.draft;
  // Legacy rows (pre-seam creates) can carry tags: null; default so the
  // preview never crashes the list view (F10 crash guard).
  const tags = entry.tags ?? [];

  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full text-left px-3 py-2.5 rounded-md transition-colors ${
        isSelected ? "bg-card shadow-sm border border-border" : "hover:bg-card/50"
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <Icon className="w-4 h-4 text-muted-foreground flex-shrink-0" />
          <div className="min-w-0">
            <div className="truncate text-sm">{entry.name}</div>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className={`text-[10px] px-1.5 py-0.5 rounded ${statusClass}`}>
                {t(`kb.status.${entry.status}`)}
              </span>
              {tags.length > 0 && (
                <span className="text-xs text-muted-foreground truncate">
                  {tags.slice(0, 3).join(", ")}
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <span className="text-[10px] text-muted-foreground">
            {formatRelativeTime(entry.updated_at)}
          </span>
          {isSelected && <ChevronRight className="w-4 h-4 text-muted-foreground" />}
        </div>
      </div>
    </button>
  );
}
