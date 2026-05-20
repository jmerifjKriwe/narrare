"use client";

import { CheckSquare, Loader2, Square } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { useChapterOutline, useUpdateOutline } from "@/lib/hooks/usePlanning";
import { debounce } from "@/lib/utils";
import type { OutlineBeat } from "@/types";

interface OutlineEditorProps {
  chapterId: string;
  novelId: string;
}

export function OutlineEditor({ chapterId, novelId }: OutlineEditorProps) {
  const t = useTranslations("studio");

  const { data: outline, isLoading } = useChapterOutline(novelId, chapterId);
  const updateMutation = useUpdateOutline(novelId);

  const [beats, setBeats] = useState<OutlineBeat[]>([]);
  const [notes, setNotes] = useState("");

  // Sync from server data
  useEffect(() => {
    if (outline) {
      setBeats(outline.planned_beats);
      setNotes(outline.outline_notes);
    }
  }, [outline]);

  // Debounced save
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const debouncedSave = useCallback(
    debounce((updatedBeats: OutlineBeat[], updatedNotes: string) => {
      updateMutation.mutate({
        chapterId,
        data: {
          planned_beats: updatedBeats,
          outline_notes: updatedNotes,
        },
      });
    }, 800),
    [],
  );

  function toggleBeat(index: number) {
    const updated = beats.map((b, i) => (i === index ? { ...b, completed: !b.completed } : b));
    setBeats(updated);
    debouncedSave(updated, notes);
  }

  function handleNotesChange(value: string) {
    setNotes(value);
    debouncedSave(beats, value);
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-4">
        <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-3 p-4">
      <h4 className="text-sm font-medium">{t("storyboard.outline.beats")}</h4>

      {beats.length === 0 ? (
        <p className="text-xs text-muted-foreground">{t("storyboard.outline.noBeats")}</p>
      ) : (
        <ul className="space-y-1.5">
          {beats.map((beat, i) => (
            <li key={`beat-${beat.title}`}>
              <button
                type="button"
                onClick={() => toggleBeat(i)}
                className="flex items-start gap-2 text-left w-full text-xs hover:bg-accent/50 rounded px-1 py-0.5 transition-colors"
              >
                {beat.completed ? (
                  <CheckSquare className="w-3.5 h-3.5 mt-0.5 text-primary flex-shrink-0" />
                ) : (
                  <Square className="w-3.5 h-3.5 mt-0.5 text-muted-foreground flex-shrink-0" />
                )}
                <span className={beat.completed ? "line-through text-muted-foreground" : ""}>
                  {beat.title}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <div>
        <label htmlFor="outline-notes" className="text-sm font-medium block mb-1">
          {t("storyboard.outline.notes")}
        </label>
        <textarea
          id="outline-notes"
          value={notes}
          onChange={(e) => handleNotesChange(e.target.value)}
          rows={4}
          className="w-full px-3 py-2 bg-background border border-border rounded-md text-xs resize-y"
        />
      </div>
    </div>
  );
}
