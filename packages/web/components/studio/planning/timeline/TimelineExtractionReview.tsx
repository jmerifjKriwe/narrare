"use client";

import { Check, Loader2, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { chaptersApi } from "@/lib/api/client";
import { useCreateTimelineEvent, useTimelineExtraction } from "@/lib/hooks/useTimeline";
import { cn } from "@/lib/utils";
import type { ExtractedEvent } from "@/types/timeline";

interface TimelineExtractionReviewProps {
  novelId: string;
  onClose?: () => void;
}

/** Review and accept/reject extracted temporal expressions from chapters. */
export function TimelineExtractionReview({ novelId, onClose }: TimelineExtractionReviewProps) {
  const t = useTranslations("timeline");
  const extractMutation = useTimelineExtraction(novelId);
  const createEventMutation = useCreateTimelineEvent(novelId);

  const [selectedChapterIds, setSelectedChapterIds] = useState<Set<string>>(new Set());
  const [chapters, setChapters] = useState<{ id: string; title: string }[]>([]);
  const [chaptersLoaded, setChaptersLoaded] = useState(false);
  const [chaptersError, setChaptersError] = useState(false);

  const [extractedEvents, setExtractedEvents] = useState<ExtractedEvent[]>([]);
  const [decisions, setDecisions] = useState<Record<string, "accepted" | "rejected">>({});

  // Load chapters for selection on first render
  if (!chaptersLoaded && !chaptersError) {
    setChaptersLoaded(true);
    chaptersApi
      .list(novelId)
      .then((result) => {
        const items = (result as unknown as { id: string; title: string }[]).map((ch) => ({
          id: ch.id,
          title: ch.title,
        }));
        setChapters(items);
      })
      .catch(() => setChaptersError(true));
  }

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
    extractMutation.mutate(ids, {
      onSuccess: (data) => {
        setExtractedEvents(data);
        setDecisions({});
      },
    });
  };

  const handleAccept = (event: ExtractedEvent) => {
    setDecisions((prev) => ({ ...prev, [event.id]: "accepted" }));
    createEventMutation.mutate({
      event_name: event.event_name,
      description: event.context,
      timestamp_raw: event.timestamp_raw,
      source: "extracted",
    });
  };

  const handleReject = (eventId: string) => {
    setDecisions((prev) => ({ ...prev, [eventId]: "rejected" }));
  };

  const isExtracting = extractMutation.isPending;
  const hasSelection = selectedChapterIds.size > 0;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
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

      {/* Chapter selection */}
      <div className="px-4 py-3 border-b border-border">
        <p className="text-xs font-medium text-muted-foreground mb-2">{t("selectChapters")}</p>

        {chaptersError ? (
          <p className="text-xs text-[var(--color-error)]">{t("errorLoading")}</p>
        ) : chapters.length === 0 && chaptersLoaded ? (
          <p className="text-xs text-muted-foreground">{t("noEvents")}</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {chapters.map((ch) => (
              <label
                key={ch.id}
                className={cn(
                  "inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-md border cursor-pointer transition-colors",
                  selectedChapterIds.has(ch.id)
                    ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                    : "border-border bg-card text-muted-foreground hover:bg-[var(--color-bg-secondary)]",
                )}
              >
                <input
                  type="checkbox"
                  checked={selectedChapterIds.has(ch.id)}
                  onChange={() => handleToggleChapter(ch.id)}
                  className="sr-only"
                />
                {ch.title}
              </label>
            ))}
          </div>
        )}

        <button
          type="button"
          onClick={handleExtract}
          disabled={!hasSelection || isExtracting}
          className="mt-3 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-[var(--color-accent)] text-white hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {isExtracting ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              {t("extracting")}
            </>
          ) : (
            t("extractButton")
          )}
        </button>

        {extractMutation.isError && (
          <p className="text-xs text-[var(--color-error)] mt-2">{t("errorExtract")}</p>
        )}
      </div>

      {/* Extracted events */}
      <div className="flex-1 overflow-auto px-4 py-3">
        {extractedEvents.length === 0 && !isExtracting && (
          <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
            {t("noExtractions")}
          </div>
        )}

        <div className="flex flex-col gap-3">
          {extractedEvents.map((event) => {
            const decision = decisions[event.id];
            const isDecided = decision !== undefined;

            return (
              <div
                key={event.id}
                className={cn(
                  "p-3 rounded-lg border border-border bg-card",
                  isDecided && "opacity-60",
                )}
              >
                {/* Expression */}
                <div className="flex items-start gap-2">
                  <span className="text-base leading-none" aria-hidden="true">
                    {"\uD83D\uDCDD"}
                  </span>
                  <span className="text-sm font-medium text-[var(--color-text-primary)]">
                    {"\u201C"}
                    {event.expression}
                    {"\u201D"}
                  </span>
                </div>

                {/* Event name */}
                <p className="text-xs text-muted-foreground mt-1">
                  {t("eventName")}: {event.event_name}
                </p>

                {/* Chapter */}
                <p className="text-xs text-muted-foreground">
                  {t("chapter")}: {event.chapter_reference}
                </p>

                {/* Characters */}
                {event.character_names.length > 0 && (
                  <div className="flex items-center gap-1 mt-1.5 flex-wrap">
                    {event.character_names.map((name) => (
                      <span
                        key={name}
                        className="inline-flex items-center px-1.5 py-0.5 text-[10px] rounded-full bg-[var(--color-bg-secondary)] text-muted-foreground"
                      >
                        {name}
                      </span>
                    ))}
                  </div>
                )}

                {/* Confidence bar */}
                <div className="flex items-center gap-2 mt-1.5">
                  <span className="text-[10px] text-muted-foreground">{t("confidence")}</span>
                  <div className="flex-1 h-1.5 bg-[var(--color-bg-secondary)] rounded-full overflow-hidden max-w-24">
                    <div
                      className="h-full bg-[var(--color-accent)] rounded-full"
                      style={{ width: `${Math.round(event.confidence * 100)}%` }}
                    />
                  </div>
                  <span className="text-[10px] text-muted-foreground">
                    {Math.round(event.confidence * 100)}%
                  </span>
                </div>

                {/* Context */}
                <p className="text-xs text-muted-foreground mt-1.5 italic leading-relaxed">
                  {t("context")}: {"\u201C"}
                  {event.context}
                  {"\u201D"}
                </p>

                {/* Accept / Reject actions */}
                <div className="flex items-center gap-2 mt-2">
                  {decision === undefined ? (
                    <>
                      <button
                        type="button"
                        onClick={() => handleAccept(event)}
                        disabled={createEventMutation.isPending}
                        className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-md border border-green-300 text-green-700 hover:bg-green-50 transition-colors disabled:opacity-50 dark:border-green-700 dark:text-green-400 dark:hover:bg-green-950"
                      >
                        <Check className="w-3 h-3" />
                        {t("accept")}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleReject(event.id)}
                        className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-md border border-red-300 text-red-700 hover:bg-red-50 transition-colors dark:border-red-700 dark:text-red-400 dark:hover:bg-red-950"
                      >
                        <X className="w-3 h-3" />
                        {t("reject")}
                      </button>
                    </>
                  ) : (
                    <span
                      className={cn(
                        "text-xs font-medium",
                        decision === "accepted"
                          ? "text-green-600 dark:text-green-400"
                          : "text-red-600 dark:text-red-400",
                      )}
                    >
                      {decision === "accepted" ? t("accepted") : t("rejected")}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
