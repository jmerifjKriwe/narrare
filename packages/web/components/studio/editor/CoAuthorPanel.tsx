"use client";

import { Check, Loader2, RotateCcw, Sparkles, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useRef, useState } from "react";
import {
  applyChanges,
  type ChangeDetail,
  type CoAuthorFocus,
  type CoAuthorRevision,
  recordFeedback,
  streamCoAuthor,
  type TextChange,
} from "@/lib/api/coauthor";
import { ChangeReview } from "./ChangeReview";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type CoAuthorPhase = "focus" | "streaming" | "review" | "done" | "error";

interface CoAuthorPanelProps {
  readonly novelId: string;
  readonly chapterId: string;
  readonly selectionText: string;
  readonly contextBefore?: string;
  readonly contextAfter?: string;
  readonly onAccept: (revisedText: string) => void;
  readonly onClose: () => void;
}

const FOCUS_OPTIONS: { value: CoAuthorFocus; labelKey: string }[] = [
  { value: "word_choice", labelKey: "coAuthor.focusWordChoice" },
  { value: "sentence", labelKey: "coAuthor.focusSentence" },
  { value: "dialogue", labelKey: "coAuthor.focusDialogue" },
  { value: "description", labelKey: "coAuthor.focusDescription" },
];

const wordCount = (text: string): number => text.trim().split(/\s+/).filter(Boolean).length;

const btnBase = "px-4 py-2.5 text-sm rounded-lg transition-all";
const btnPrimary = `${btnBase} bg-primary text-primary-foreground hover:opacity-90 shadow-sm font-medium`;
const btnSecondary = `${btnBase} border border-border hover:bg-accent`;
const btnSm = "px-3 py-1 text-xs font-medium rounded-md transition-all";

// ---------------------------------------------------------------------------
// Focus Selector
// ---------------------------------------------------------------------------

function FocusSelector({
  selectedFocus,
  onToggle,
  selectionText,
  onStart,
}: {
  selectedFocus: CoAuthorFocus[];
  onToggle: (v: CoAuthorFocus) => void;
  selectionText: string;
  onStart: () => void;
}) {
  const t = useTranslations("studio");
  return (
    <div className="space-y-6">
      <p className="text-sm text-muted-foreground">
        {t("coAuthor.selectionWords", { count: wordCount(selectionText) })}
      </p>
      <div>
        <p className="text-sm font-medium mb-3">{t("coAuthor.focusLabel")}</p>
        <div className="flex flex-wrap gap-2">
          {FOCUS_OPTIONS.map((opt) => {
            const active = selectedFocus.includes(opt.value);
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => onToggle(opt.value)}
                className={`px-4 py-2 text-sm font-medium rounded-lg border transition-all ${
                  active
                    ? "border-primary bg-primary/10 text-primary shadow-sm"
                    : "border-border hover:border-primary/50 text-foreground"
                }`}
              >
                {t(opt.labelKey)}
              </button>
            );
          })}
        </div>
      </div>
      <button
        type="button"
        onClick={onStart}
        disabled={selectedFocus.length === 0}
        className={`${btnPrimary} flex items-center justify-center gap-2 w-full disabled:opacity-50`}
      >
        <Sparkles className="w-4 h-4" />
        <span>{t("coAuthor.start")}</span>
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Streaming phase
// ---------------------------------------------------------------------------

function StreamingPhase({ streamedText, onStop }: { streamedText: string; onStop: () => void }) {
  const t = useTranslations("studio");
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 p-4 rounded-lg bg-muted/50">
        <Loader2 className="w-5 h-5 animate-spin text-primary" />
        <div>
          <p className="text-sm font-medium">{t("coAuthor.streaming")}</p>
          {streamedText.trim().length > 0 && (
            <p className="text-xs text-muted-foreground mt-1">
              {t("coAuthor.wordsReceived", { count: wordCount(streamedText) })}
            </p>
          )}
        </div>
      </div>
      {streamedText.trim().length > 0 && (
        <div className="p-3 rounded-lg border border-border bg-card text-sm leading-relaxed max-h-60 overflow-y-auto">
          {streamedText}
        </div>
      )}
      <button
        type="button"
        onClick={onStop}
        className={`${btnSecondary} flex items-center justify-center gap-2 w-full`}
      >
        <X className="w-4 h-4" />
        <span>{t("coAuthor.stop")}</span>
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Review phase
// ---------------------------------------------------------------------------

function ReviewPhase({
  changes,
  acceptance,
  reasoning,
  onToggleChange,
  onAcceptAll,
  onRejectAll,
  onApply,
  submitting,
  onClose,
}: {
  changes: ChangeDetail[];
  acceptance: Record<string, boolean>;
  reasoning: string;
  onToggleChange: (id: string) => void;
  onAcceptAll: () => void;
  onRejectAll: () => void;
  onApply: () => void;
  submitting: boolean;
  onClose: () => void;
}) {
  const t = useTranslations("studio");
  const allAccepted = changes.length > 0 && changes.every((c) => acceptance[c.id] !== false);
  const allRejected = changes.length > 0 && changes.every((c) => acceptance[c.id] === false);
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between p-3 rounded-lg bg-primary/5 border border-primary/20">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-primary" />
          <p className="text-sm font-medium">
            {t("coAuthor.improvementsFound", { count: changes.length })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onAcceptAll}
            className={`${btnSm} ${allAccepted ? "bg-primary text-primary-foreground shadow-sm" : "border border-border hover:bg-accent"}`}
          >
            {t("coAuthor.acceptAll")}
          </button>
          <button
            type="button"
            onClick={onRejectAll}
            className={`${btnSm} ${allRejected ? "bg-destructive/10 text-destructive border border-destructive/30" : "border border-border hover:bg-accent"}`}
          >
            {t("coAuthor.rejectAll")}
          </button>
        </div>
      </div>
      {reasoning && (
        <details className="group">
          <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground select-none">
            {t("coAuthor.reasoning")}
          </summary>
          <p className="mt-1.5 text-sm text-muted-foreground bg-muted/30 rounded-lg p-3">
            {reasoning}
          </p>
        </details>
      )}
      <div className="space-y-3 max-h-80 overflow-y-auto">
        {changes.map((c) => (
          <ChangeReview
            key={c.id}
            change={c}
            isAccepted={acceptance[c.id] !== false}
            onToggle={onToggleChange}
          />
        ))}
      </div>
      <div className="flex items-center gap-2 pt-2">
        <button type="button" onClick={onClose} className={`${btnSecondary} flex-1`}>
          {t("coAuthor.cancel")}
        </button>
        <button
          type="button"
          onClick={onApply}
          disabled={submitting}
          className={`${btnPrimary} flex-1 flex items-center justify-center gap-2 disabled:opacity-50`}
        >
          {submitting ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Check className="w-4 h-4" />
          )}
          <span>{allAccepted ? t("coAuthor.acceptAll") : t("coAuthor.applySelected")}</span>
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Done phase
// ---------------------------------------------------------------------------

function DonePhase({ onClose }: { onClose: () => void }) {
  const t = useTranslations("studio");
  return (
    <div className="flex flex-col items-center justify-center py-8 space-y-4">
      <div className="w-12 h-12 rounded-full bg-green-500/10 flex items-center justify-center">
        <Check className="w-6 h-6 text-green-500" />
      </div>
      <p className="text-sm font-medium">{t("coAuthor.done")}</p>
      <button type="button" onClick={onClose} className={`${btnSecondary}`}>
        {t("coAuthor.close")}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function CoAuthorPanel({
  novelId,
  chapterId,
  selectionText,
  contextBefore,
  contextAfter,
  onAccept,
  onClose,
}: CoAuthorPanelProps) {
  const t = useTranslations("studio");
  const [phase, setPhase] = useState<CoAuthorPhase>("focus");
  const [selectedFocus, setSelectedFocus] = useState<CoAuthorFocus[]>(["word_choice"]);
  const [streamedText, setStreamedText] = useState("");
  const [changes, setChanges] = useState<ChangeDetail[]>([]);
  const [reasoning, setReasoning] = useState("");
  const [requestId, setRequestId] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [acceptance, setAcceptance] = useState<Record<string, boolean>>({});
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const toggleFocus = useCallback((value: CoAuthorFocus) => {
    setSelectedFocus((prev) => {
      if (prev.includes(value)) return prev.length <= 1 ? prev : prev.filter((f) => f !== value);
      return [...prev, value];
    });
  }, []);

  const handleStart = useCallback(() => {
    if (selectedFocus.length === 0) return;
    setPhase("streaming");
    setStreamedText("");
    setChanges([]);
    setReasoning("");
    setErrorMsg(null);

    // Generate correlation UUID for apply/feedback
    setRequestId(crypto.randomUUID());

    const controller = new AbortController();
    abortRef.current = controller;

    streamCoAuthor(
      chapterId,
      novelId,
      {
        selection_text: selectionText,
        context_before: contextBefore,
        context_after: contextAfter,
        focus: selectedFocus,
      },
      {
        onChunk: (text) => setStreamedText((prev) => prev + text),
        onComplete: (revision: CoAuthorRevision) => {
          setChanges(revision.changes);
          setReasoning(revision.reasoning);
          // Use backend-generated request_id if available
          if (revision.request_id) setRequestId(revision.request_id);
          // Init acceptance: all changes accepted by default
          const initial: Record<string, boolean> = {};
          revision.changes.forEach((c) => {
            initial[c.id] = true;
          });
          setAcceptance(initial);
          setPhase(revision.changes.length > 0 ? "review" : "done");
          abortRef.current = null;
        },
        onError: (err) => {
          if (err.message.includes("Abort")) return;
          setErrorMsg(err.message || t("coAuthor.errorGeneric"));
          setPhase("error");
          abortRef.current = null;
        },
      },
      controller.signal,
    );
  }, [selectedFocus, chapterId, novelId, selectionText, contextBefore, contextAfter, t]);

  const handleAcceptAll = useCallback(() => {
    const all: Record<string, boolean> = {};
    changes.forEach((c) => {
      all[c.id] = true;
    });
    setAcceptance(all);
  }, [changes]);

  const handleRejectAll = useCallback(() => {
    const all: Record<string, boolean> = {};
    changes.forEach((c) => {
      all[c.id] = false;
    });
    setAcceptance(all);
  }, [changes]);

  const handleToggleChange = useCallback((id: string) => {
    setAcceptance((prev) => ({ ...prev, [id]: !prev[id] }));
  }, []);

  const handleApply = useCallback(async () => {
    const allAccepted = changes.length === 0 || changes.every((c) => acceptance[c.id] !== false);

    if (allAccepted) {
      // Full apply — no API call needed, text is already complete
      onAccept(streamedText);
      setPhase("done");
      return;
    }

    // Partial apply — only accepted changes via API (SET-005)
    setSubmitting(true);
    try {
      const acceptedChanges: TextChange[] = changes
        .filter((c) => acceptance[c.id] !== false)
        .map((c) => ({ original_text: c.original_text, revised_text: c.revised_text }));
      const rejectedChanges: TextChange[] = changes
        .filter((c) => acceptance[c.id] === false)
        .map((c) => ({ original_text: c.original_text, revised_text: c.revised_text }));

      const result = await applyChanges(chapterId, novelId, {
        request_id: requestId || crypto.randomUUID(),
        original: selectionText,
        accepted: acceptedChanges,
        rejected: rejectedChanges,
      });

      // Fire-and-forget feedback (LEARN-001) — best-effort for preference learning
      const feedback = changes.map((c) => ({
        change_id: c.id,
        action: (acceptance[c.id] !== false ? "accepted" : "rejected") as "accepted" | "rejected",
        focus: c.change_type,
        original: c.original_text,
        revised: acceptance[c.id] !== false ? c.revised_text : "",
      }));
      recordFeedback(chapterId, novelId, {
        request_id: requestId || crypto.randomUUID(),
        feedback,
      }).catch(() => {
        /* silent — feedback is best-effort */
      });

      onAccept(result.content);
      setPhase("done");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : t("coAuthor.errorGeneric"));
      setPhase("error");
    } finally {
      setSubmitting(false);
    }
  }, [
    acceptance,
    changes,
    chapterId,
    novelId,
    selectionText,
    streamedText,
    requestId,
    onAccept,
    t,
  ]);

  const handleCancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    onClose();
  }, [onClose]);

  const handleStop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setPhase(streamedText.trim().length > 0 ? "review" : "focus");
  }, [streamedText]);

  const handleRetry = useCallback(() => {
    setPhase("focus");
    setErrorMsg(null);
  }, []);

  const phaseLabel =
    phase === "streaming"
      ? `· ${t("coAuthor.streaming")}`
      : phase === "review"
        ? `· ${t("coAuthor.reviewPhase")}`
        : null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-card border border-border rounded-xl shadow-2xl max-w-lg w-full overflow-hidden">
        <div className="p-5 border-b border-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-primary" />
            <h3 className="font-medium">{t("coAuthor.title")}</h3>
            {phaseLabel && <span className="text-xs text-muted-foreground ml-1">{phaseLabel}</span>}
          </div>
          <button
            type="button"
            onClick={handleCancel}
            className="p-1 rounded-md hover:bg-accent transition-colors"
            aria-label={t("coAuthor.close")}
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-5">
          {phase === "focus" && (
            <FocusSelector
              selectedFocus={selectedFocus}
              onToggle={toggleFocus}
              selectionText={selectionText}
              onStart={handleStart}
            />
          )}
          {phase === "streaming" && (
            <StreamingPhase streamedText={streamedText} onStop={handleStop} />
          )}
          {phase === "review" && (
            <ReviewPhase
              changes={changes}
              acceptance={acceptance}
              reasoning={reasoning}
              onToggleChange={handleToggleChange}
              onAcceptAll={handleAcceptAll}
              onRejectAll={handleRejectAll}
              onApply={handleApply}
              submitting={submitting}
              onClose={handleCancel}
            />
          )}
          {phase === "done" && <DonePhase onClose={onClose} />}
          {phase === "error" && (
            <div className="space-y-4">
              <div
                className="bg-destructive/10 text-destructive rounded-lg p-3 text-sm"
                role="alert"
              >
                {errorMsg || t("coAuthor.errorGeneric")}
              </div>
              <div className="flex gap-2">
                <button type="button" onClick={handleCancel} className={`${btnSecondary} flex-1`}>
                  {t("coAuthor.close")}
                </button>
                <button
                  type="button"
                  onClick={handleRetry}
                  className={`${btnPrimary} flex-1 flex items-center justify-center gap-2`}
                >
                  <RotateCcw className="w-4 h-4" />
                  <span>{t("coAuthor.retry")}</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
