"use client";

import { Loader2, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { chaptersApi } from "@/lib/api/client";
import { useConfirmExtractedEvent, useSSEExtraction } from "@/lib/hooks/useTimeline";
import type { ExtractedEvent } from "@/types/timeline";
import { ChapterSelector } from "./ChapterSelector";
import { ExtractedEventCard } from "./ExtractedEventCard";

interface TimelineExtractionReviewProps {
  novelId: string;
  onClose?: () => void;
}

/** Review and accept/reject extracted temporal expressions from chapters. */
export function TimelineExtractionReview({ novelId, onClose }: TimelineExtractionReviewProps) {
  const t = useTranslations("timeline");
  const {
    isExtracting,
    extractedEvents,
    extractError,
    startExtraction,
    reset: resetExtraction,
  } = useSSEExtraction(novelId);
  const confirmMutation = useConfirmExtractedEvent(novelId);

  const [selectedChapterIds, setSelectedChapterIds] = useState<Set<string>>(new Set());
  const [chapters, setChapters] = useState<{ id: string; title: string }[]>([]);
  const [chaptersLoaded, setChaptersLoaded] = useState(false);
  const [chaptersError, setChaptersError] = useState(false);
  const [decisions, setDecisions] = useState<Record<string, "accepted" | "rejected">>({});

  // Load chapters for selection on first render
  useEffect(() => {
    if (!chaptersLoaded && !chaptersError) {
      setChaptersLoaded(true);
      chaptersApi
        .list(novelId)
        .then((result) => {
          const items = (result as unknown as { id: string; title: string }[]).map((chapter) => ({
            id: chapter.id,
            title: chapter.title,
          }));
          setChapters(items);
        })
        .catch(() => setChaptersError(true));
    }
  }, [novelId, chaptersLoaded, chaptersError]);

  const handleToggleChapter = (chapterId: string) => {
    setSelectedChapterIds((prev) => {
      const next = new Set(prev);
      if (next.has(chapterId)) {
        next.delete(chapterId);
      } else {
        next.add(chapterId);
      }
      return next;
    });
  };

  const handleExtract = () => {
    const ids = Array.from(selectedChapterIds);
    resetExtraction();
    setDecisions({});
    startExtraction(ids);
  };

  const handleAccept = (event: ExtractedEvent) => {
    setDecisions((prev) => ({ ...prev, [event.id]: "accepted" }));
    confirmMutation.mutate(event);
  };

  const handleReject = (eventId: string) => {
    setDecisions((prev) => ({ ...prev, [eventId]: "rejected" }));
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-card">
        <h3 className="text-sm font-medium">{t("extractTitle")}</h3>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded hover:bg-[var(--color-bg-secondary)] transition-colors text-muted-foreground"
            aria-label={t("close")}
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      <ChapterSelector
        chapters={chapters}
        chaptersLoaded={chaptersLoaded}
        chaptersError={chaptersError}
        selectedChapterIds={selectedChapterIds}
        isExtracting={isExtracting}
        extractError={extractError?.userMessage ?? null}
        onToggleChapter={handleToggleChapter}
        onExtract={handleExtract}
      />

      <div className="flex-1 overflow-auto px-4 py-3">
        {isExtracting && extractedEvents.length === 0 && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
          </div>
        )}

        {extractedEvents.length === 0 && !isExtracting && (
          <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
            {t("noExtractions")}
          </div>
        )}

        {isExtracting && extractedEvents.length > 0 && (
          <p className="text-xs text-muted-foreground mb-3">
            {t("extractedCount", { count: extractedEvents.length })}
          </p>
        )}

        <div className="flex flex-col gap-3">
          {extractedEvents.map((event) => (
            <ExtractedEventCard
              key={event.id}
              event={event}
              decision={decisions[event.id]}
              isConfirmPending={confirmMutation.isPending}
              onAccept={handleAccept}
              onReject={handleReject}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
