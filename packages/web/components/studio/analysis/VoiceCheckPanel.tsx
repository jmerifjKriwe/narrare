"use client";

/**
 * VoiceCheckPanel — on-demand side panel for the Voice Consistency Checker
 * (WRITE-010).
 *
 * Unlike the character-voice panel (which auto-runs on mount), this panel is
 * **on-demand**: the user clicks the {@link VoiceCheckTrigger} to run the
 * check. The flag+score report is shown here only — NO inline editor
 * decorations (ADR-057 / §5.1).
 *
 * Lifecycle runs through {@link useCharacterVoiceCheck} → `useAIOperation`
 * (ADR-043): no manual AbortController, SSE streaming via the voice-check
 * stream client (§5.1 — REST-only is forbidden). Follows the CharacterVoicePanel
 * layout (400px wide, border-left). The results view is extracted into
 * {@link ./_components/VoiceCheckResults} per RULE-04.
 *
 * Page/store wiring (mounting this panel + toolbar trigger) is a separate step
 * (4c); this panel takes `chapterId` + `onClose` props and is self-contained.
 */

import { ArrowLeft, BadgeCheck, Info, Loader2, RefreshCw, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { AnalysisPanelWrapper } from "@/components/ui/analysis-panel-wrapper";
import { useCharacterVoiceCheck } from "@/lib/hooks/useCharacterVoiceCheck";
import { VoiceCheckResults } from "./_components/VoiceCheckResults";
import { VoiceCheckTrigger } from "./VoiceCheckTrigger";

// --- Types ---

interface VoiceCheckPanelProps {
  /** Chapter to check (null disables the trigger). */
  chapterId: string | null;
  onClose: () => void;
}

type ViewState = "idle" | "loading" | "results" | "error";

// --- Component ---

export function VoiceCheckPanel({ chapterId, onClose }: VoiceCheckPanelProps) {
  const t = useTranslations("analysis");

  const { results, error, progress, run, isLoading, isStreaming, isComplete, isError } =
    useCharacterVoiceCheck();

  const inFlight = isLoading || isStreaming;

  const viewState: ViewState = isError
    ? "error"
    : inFlight
      ? "loading"
      : isComplete && results
        ? "results"
        : "idle";

  const handleRun = () => {
    if (chapterId) run(chapterId);
  };

  return (
    <div className="flex flex-col h-full border-l border-border bg-background w-[400px] min-w-[400px]">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border bg-card">
        <div className="flex items-center gap-3 min-w-0">
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-muted-foreground hover:text-foreground rounded-md hover:bg-muted transition-colors"
            aria-label={t("close")}
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="flex items-center gap-2 min-w-0">
            <BadgeCheck className="w-5 h-5 text-violet-500 flex-shrink-0" />
            <h3 className="font-medium truncate">{t("voiceCheck.title")}</h3>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="p-1.5 text-muted-foreground hover:text-foreground rounded-md hover:bg-muted transition-colors"
          aria-label={t("close")}
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Description banner */}
      <div className="px-4 py-1.5 border-b border-border bg-muted/30">
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Info className="w-3.5 h-3.5 flex-shrink-0" />
          {t("voiceCheck.description")}
        </p>
      </div>

      {/* AI disclaimer banner */}
      <div className="px-4 py-1.5 border-b border-border bg-muted/30">
        <p className="text-xs text-muted-foreground">{t("voiceCheck.aiDisclaimer")}</p>
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto p-6 space-y-4">
          <AnalysisPanelWrapper phase={viewState}>
            {/* Idle — on-demand trigger CTA */}
            {viewState === "idle" && (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="w-16 h-16 rounded-full bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center mb-6">
                  <BadgeCheck className="w-8 h-8 text-violet-500" />
                </div>
                <VoiceCheckTrigger onClick={handleRun} disabled={!chapterId} isLoading={inFlight} />
              </div>
            )}

            {/* Loading state */}
            {viewState === "loading" && (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="relative mb-6">
                  <div className="w-16 h-16 rounded-full bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center">
                    <Loader2 className="w-8 h-8 text-violet-500 animate-spin" />
                  </div>
                </div>
                <p className="text-lg font-medium mb-2">{t("voiceCheck.analyzing")}</p>
                <p className="text-sm text-muted-foreground">
                  {progress ?? t("voiceCheck.analyzingSubtext")}
                </p>
              </div>
            )}

            {/* Error state */}
            {viewState === "error" && (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="w-12 h-12 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center mb-4">
                  <Info className="w-6 h-6 text-red-500" />
                </div>
                <p className="text-lg font-medium mb-1">{t("voiceCheck.analysisFailed")}</p>
                <p className="text-sm text-muted-foreground mb-4">{error?.userMessage}</p>
                <button
                  type="button"
                  onClick={handleRun}
                  className="flex items-center gap-1.5 px-4 py-2 text-sm border border-border rounded-md hover:bg-muted transition-colors"
                >
                  <RefreshCw className="w-4 h-4" />
                  {t("voiceCheck.retry")}
                </button>
              </div>
            )}

            {/* Results */}
            {viewState === "results" && results && (
              <>
                <div className="flex justify-end">
                  <VoiceCheckTrigger
                    onClick={handleRun}
                    disabled={!chapterId}
                    isLoading={inFlight}
                  />
                </div>
                <VoiceCheckResults results={results} t={t} />
              </>
            )}
          </AnalysisPanelWrapper>
        </div>
      </div>
    </div>
  );
}
