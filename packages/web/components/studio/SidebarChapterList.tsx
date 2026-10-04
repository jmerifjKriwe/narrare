"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef } from "react";
import { chaptersApi, volumesApi } from "@/lib/api/client";
import { useEditorStore } from "@/lib/stores/editorStore";
import { ImportLaunchSection } from "./importing/ImportLaunchSection";

/**
 * SidebarChapterList — Chapter list with volume selector for the sidebar.
 *
 * Owns all chapter-related queries, mutations, and localStorage persistence.
 * Extracted from Sidebar.tsx (RULE-04); the import→extraction launch pipeline
 * (modal, failure/suggestion banners, bulk panel host) lives in
 * importing/ImportLaunchSection.tsx (F2 T8) — copy single-sourced from the
 * "importing" namespace.
 */

export function SidebarChapterList({ novelId }: { novelId: string }) {
  const t = useTranslations("studio");
  const queryClient = useQueryClient();
  const activeChapterId = useEditorStore((s) => s.activeChapterId);
  const setActiveChapterId = useEditorStore((s) => s.setActiveChapterId);
  const activeVolumeId = useEditorStore((s) => s.activeVolumeId);
  const setActiveVolumeId = useEditorStore((s) => s.setActiveVolumeId);

  // Fetch volumes for volume selector
  const { data: volumes = [] } = useQuery({
    queryKey: ["novels", novelId, "volumes"],
    queryFn: () => volumesApi.list(novelId),
    enabled: !!novelId,
  });

  // Fetch chapters for current novel, optionally filtered by volume
  const { data: chapters = [] } = useQuery({
    queryKey: ["novels", novelId, "chapters", activeVolumeId],
    queryFn: () => chaptersApi.list(novelId, activeVolumeId ?? undefined),
    enabled: !!novelId,
  });

  // Create chapter mutation
  const createChapterMutation = useMutation({
    mutationFn: () =>
      chaptersApi.create(novelId, {
        title: t("sidebar.newChapterTitle"),
        ...(activeVolumeId ? { volume_id: activeVolumeId } : {}),
      }),
    onSuccess: (chapter) => {
      setActiveChapterId(chapter.id);
      queryClient.invalidateQueries({
        queryKey: ["novels", novelId!, "chapters"],
      });
    },
  });

  // Reset active chapter when novelId changes (user navigates to a different novel)
  const prevNovelIdRef = useRef(novelId);
  useEffect(() => {
    if (prevNovelIdRef.current !== novelId) {
      setActiveChapterId(null);
      prevNovelIdRef.current = novelId;
    }
  }, [novelId, setActiveChapterId]);

  // Build a stable chapter-id set for O(1) lookups
  const chapterIds = useCallback(() => new Set(chapters.map((c) => c.id)), [chapters]);

  // Restore last-active chapter from localStorage, or fall back to first chapter
  useEffect(() => {
    if (!novelId || chapters.length === 0 || activeChapterId) return;
    const key = `narrare:lastChapter:${novelId}`;
    const stored = localStorage.getItem(key);
    if (stored && chapterIds().has(stored)) {
      setActiveChapterId(stored);
    } else {
      setActiveChapterId(chapters[0].id);
    }
  }, [novelId, chapters, activeChapterId, setActiveChapterId, chapterIds]);

  // Persist active chapter to localStorage whenever it changes
  useEffect(() => {
    if (!novelId || !activeChapterId) return;
    localStorage.setItem(`narrare:lastChapter:${novelId}`, activeChapterId);
  }, [novelId, activeChapterId]);

  return (
    <>
      {/* Volume selector — hidden when only default volume exists */}
      {volumes.length > 1 && (
        <div className="px-3 py-2 border-b border-border">
          <select
            value={activeVolumeId ?? ""}
            onChange={(e) => setActiveVolumeId(e.target.value || null)}
            className="w-full px-3 py-1.5 text-sm bg-card border border-border rounded-md"
            aria-label={t("volumes.title")}
          >
            <option value="">{t("volumes.allVolumes")}</option>
            {volumes.map((v) => (
              <option key={v.id} value={v.id}>
                {v.title}
              </option>
            ))}
          </select>
        </div>
      )}
      <div className="px-3 py-2 border-b border-border">
        <p className="text-xs text-muted-foreground px-4 py-1 uppercase">{t("sidebar.chapters")}</p>
      </div>
      <div className="flex-1 overflow-y-auto p-3">
        <div className="space-y-1">
          {chapters.map((chapter) => {
            const isActive = chapter.id === activeChapterId;
            return (
              <button
                type="button"
                key={chapter.id}
                data-testid="chapter-item"
                onClick={() => setActiveChapterId(chapter.id)}
                className={`w-full text-left px-4 py-3 rounded-md transition-colors ${
                  isActive
                    ? "bg-card shadow-sm border border-border"
                    : "hover:bg-accent border border-transparent"
                }`}
              >
                <div className="truncate text-sm">{chapter.title}</div>
                <div className="text-xs text-muted-foreground mt-1">
                  {t("sidebar.words", { count: chapter.word_count })}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      <div className="p-4 border-t border-border">
        <button
          type="button"
          data-testid="new-chapter-btn"
          onClick={() => createChapterMutation.mutate()}
          disabled={createChapterMutation.isPending}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity shadow-sm disabled:opacity-50"
        >
          <Plus className="w-4 h-4" />
          <span className="text-sm">{t("sidebar.newChapter")}</span>
        </button>
        {/* Import entry + bulk extraction launch pipeline (F2 T8): failure /
            suggestion banners, ImportModal, and the BulkExtractionPanel host —
            composed in importing/ImportLaunchSection (RULE-04). */}
        <ImportLaunchSection novelId={novelId} />
      </div>
    </>
  );
}
