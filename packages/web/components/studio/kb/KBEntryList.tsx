"use client";

/**
 * KB Entry List — Column 2 of the 3-column KB browser.
 *
 * Shows search bar, "New Entry" button, and filtered entry cards.
 */

import { ChevronRight, Plus, Search } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import type { KBEntityType, KBEntry } from "@/lib/api/kb";
import { useKBDebouncedSearch } from "@/lib/hooks/useKB";
import { formatRelativeTime, STATUS_COLORS, TYPE_ICONS } from "./constants";

interface KBEntryListProps {
  novelId: string;
  entries: KBEntry[];
  isLoading: boolean;
  selectedEntryId: string | null;
  activeType: KBEntityType | null;
  onSelectEntry: (entryId: string) => void;
  onCreateNew: () => void;
}

export function KBEntryList({
  novelId,
  entries,
  isLoading,
  selectedEntryId,
  activeType,
  onSelectEntry,
  onCreateNew,
}: KBEntryListProps) {
  const t = useTranslations("studio");
  const [searchQuery, setSearchQuery] = useState("");
  const { setQuery, data: searchResults, isLoading: isSearching } = useKBDebouncedSearch(novelId);

  const displayEntries = searchQuery.length > 0 ? (searchResults?.items ?? []) : entries;
  const ActiveIcon = activeType ? TYPE_ICONS[activeType] : Search;

  function handleSearchChange(value: string) {
    setSearchQuery(value);
    setQuery(value);
  }

  return (
    <div className="w-64 border-r border-border bg-muted/30 flex flex-col">
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
        <div className="relative">
          <Search className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder={t("kb.search")}
            className="w-full pl-8 pr-3 py-2 bg-input-background border border-border rounded-md text-sm"
          />
        </div>
      </div>

      {/* Entry list */}
      <div className="flex-1 overflow-y-auto p-2">
        {(isLoading || isSearching) && (
          <div className="text-center py-8 text-muted-foreground text-sm">{t("kb.search")}</div>
        )}

        {!isLoading && !isSearching && displayEntries.length === 0 && (
          <div className="text-center py-12 text-muted-foreground text-sm">
            <ActiveIcon className="w-8 h-8 mx-auto mb-2 opacity-20" />
            <p>{t("kb.noEntries")}</p>
          </div>
        )}

        {!isLoading && !isSearching && displayEntries.length > 0 && (
          <div className="space-y-0.5">
            {displayEntries.map((entry) => (
              <EntryCard
                key={entry.id}
                entry={entry}
                isSelected={selectedEntryId === entry.id}
                onClick={() => onSelectEntry(entry.id)}
              />
            ))}
          </div>
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

  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full text-left px-3 py-2.5 rounded-md transition-all ${
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
              {entry.tags.length > 0 && (
                <span className="text-xs text-muted-foreground truncate">
                  {entry.tags.slice(0, 3).join(", ")}
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
