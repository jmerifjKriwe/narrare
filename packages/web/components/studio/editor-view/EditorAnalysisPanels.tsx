"use client";

/**
 * EditorAnalysisPanels — exhaustive switch over the analysis-panel subset of
 * {@link EditorRightPanelId}.
 *
 * Extracted from {@link EditorPanelContent} per RULE-04: the analysis cases
 * (beta reader, readability, POV, coreference, character voice, voice check,
 * voice drift, author voice, sentiment, consistency) grew large enough that
 * the combined switch exceeded the 200-line component limit. Each analysis
 * panel is on-demand and shares the same `novelId` / `activeChapterId` /
 * `closePanel` wiring shape, so they cluster naturally here. The exhaustive
 * `never` default keeps the switch compile-checked against
 * {@link AnalysisPanelId}.
 *
 * @module EditorAnalysisPanels
 */

import type { AnalysisPanelId, EditorRightPanelId } from "@/lib/stores/editorRightPanelState";
import type { ChapterSummary } from "@/types";
import { AuthorVoiceDriftPanel } from "../analysis/AuthorVoiceDriftPanel";
import { AuthorVoicePanel } from "../analysis/AuthorVoicePanel";
import { BetaReaderPanel } from "../analysis/BetaReaderPanel";
import { CharacterVoicePanel } from "../analysis/CharacterVoicePanel";
import { ConsistencyPanel } from "../analysis/ConsistencyPanel";
import { CoreferencePanel } from "../analysis/CoreferencePanel";
import { POVPanel } from "../analysis/POVPanel";
import { ReadabilityPanel } from "../analysis/ReadabilityPanel";
import { SentimentPanel } from "../analysis/SentimentPanel";
import { VoiceCheckPanel } from "../analysis/VoiceCheckPanel";
import { VoiceDriftPanel } from "../analysis/VoiceDriftPanel";

export interface EditorAnalysisPanelsProps {
  /** The active analysis panel id (narrowed by {@link EditorPanelContent}). */
  panel: AnalysisPanelId;
  novelId: string;
  activeChapterId: string;
  /** All chapters — only {@link AuthorVoicePanel} consumes this (novel-scoped). */
  chapters: ChapterSummary[];
  closePanel: (panel?: EditorRightPanelId) => void;
}

export function EditorAnalysisPanels({
  panel,
  novelId,
  activeChapterId,
  chapters,
  closePanel,
}: EditorAnalysisPanelsProps) {
  switch (panel) {
    case "beta_reader":
      return (
        <BetaReaderPanel
          novelId={novelId}
          chapterIds={[activeChapterId]}
          onClose={() => closePanel("beta_reader")}
        />
      );
    case "readability":
      return (
        <ReadabilityPanel
          novelId={novelId}
          chapterIds={[activeChapterId]}
          onClose={() => closePanel("readability")}
        />
      );
    case "pov":
      return (
        <POVPanel
          novelId={novelId}
          chapterIds={[activeChapterId]}
          onClose={() => closePanel("pov")}
        />
      );
    case "coreference":
      return (
        <CoreferencePanel
          novelId={novelId}
          chapterIds={[activeChapterId]}
          onClose={() => closePanel("coreference")}
        />
      );
    case "character_voice":
      return (
        <CharacterVoicePanel
          novelId={novelId}
          chapterIds={[activeChapterId]}
          onClose={() => closePanel("character_voice")}
        />
      );
    case "voice_check":
      return (
        <VoiceCheckPanel chapterId={activeChapterId} onClose={() => closePanel("voice_check")} />
      );
    case "voice_drift":
      return <VoiceDriftPanel novelId={novelId} onClose={() => closePanel("voice_drift")} />;
    case "author_voice":
      return (
        <AuthorVoicePanel
          novelId={novelId}
          chapters={chapters}
          onClose={() => closePanel("author_voice")}
        />
      );
    case "author_voice_drift":
      return (
        <AuthorVoiceDriftPanel novelId={novelId} onClose={() => closePanel("author_voice_drift")} />
      );
    case "sentiment":
      return (
        <SentimentPanel
          novelId={novelId}
          chapterIds={[activeChapterId]}
          onClose={() => closePanel("sentiment")}
        />
      );
    case "consistency":
      return (
        <ConsistencyPanel
          novelId={novelId}
          chapterIds={[activeChapterId]}
          onClose={() => closePanel("consistency")}
        />
      );
    default: {
      const _exhaustive: never = panel;
      return _exhaustive;
    }
  }
}
