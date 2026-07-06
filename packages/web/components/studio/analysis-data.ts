import { BookOpen, Clock, TrendingUp, Users } from "lucide-react";

export type AnalysisType = "readability" | "pacing" | "characters" | "timeline";

interface AnalysisTypeConfig {
  id: AnalysisType;
  icon: typeof BookOpen;
  titleKey: string;
  descriptionKey: string;
  /** i18n key for the "use in editor" call-to-action shown in the expanded panel. */
  editorHintKey: string;
}

export const ANALYSIS_TYPES: AnalysisTypeConfig[] = [
  {
    id: "readability",
    icon: BookOpen,
    titleKey: "analysis.readability.title",
    descriptionKey: "analysis.readability.description",
    editorHintKey: "analysis.readability.editorHint",
  },
  {
    id: "pacing",
    icon: TrendingUp,
    titleKey: "analysis.pacing.title",
    descriptionKey: "analysis.pacing.description",
    editorHintKey: "analysis.pacing.editorHint",
  },
  {
    id: "characters",
    icon: Users,
    titleKey: "analysis.characterAnalysis.title",
    descriptionKey: "analysis.characterAnalysis.description",
    editorHintKey: "analysis.characterAnalysis.editorHint",
  },
  {
    id: "timeline",
    icon: Clock,
    titleKey: "analysis.timeline.title",
    descriptionKey: "analysis.timeline.description",
    editorHintKey: "analysis.timeline.editorHint",
  },
];
