"use client";

/**
 * POVPanel — collapsible side panel for POV Analysis (ANAL-004).
 *
 * Shows POV distribution chart, scene map with confidence badges,
 * issues list with severity/type icons, and summary stats.
 * Follows ReadabilityPanel layout (400px wide, border-left).
 */

import {
  AlertTriangle,
  ArrowLeft,
  ChevronDown,
  ChevronUp,
  Eye,
  Info,
  Loader2,
  RefreshCw,
  X,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import type { POVIssue, POVResult, POVScene } from "@/lib/api/analysis";
import { usePOVAnalysis } from "@/lib/hooks/usePOV";

// --- Types ---

interface POVPanelProps {
  novelId: string;
  chapterIds: string[];
  onClose: () => void;
}

// --- Helpers ---

/** Confidence badge color based on score. */
function getConfidenceColorClass(confidence: number): string {
  if (confidence >= 0.8)
    return "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400";
  if (confidence >= 0.5)
    return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400";
  return "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400";
}

/** Severity icon + color. */
function SeverityIcon({ severity }: { severity: POVIssue["severity"] }) {
  if (severity === "error") {
    return <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0" />;
  }
  return <AlertTriangle className="w-4 h-4 text-yellow-500 flex-shrink-0" />;
}

/** Issue type badge color. */
function getIssueTypeBadgeClass(type: POVIssue["type"]): string {
  switch (type) {
    case "head_hop":
      return "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400";
    case "knowledge_leak":
      return "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400";
    case "emotional_leak":
      return "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400";
    case "physical_impossibility":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400";
  }
}

// --- Sub-components ---

/** Horizontal bar showing a character's POV percentage. */
function DistributionBar({ character, percentage }: { character: string; percentage: number }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium truncate">{character}</span>
        <span className="text-xs text-muted-foreground flex-shrink-0 ml-2">
          {percentage.toFixed(1)}%
        </span>
      </div>
      <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
        <div
          className="h-full rounded-full bg-primary transition-all duration-500"
          style={{ width: `${Math.min(100, percentage)}%` }}
        />
      </div>
    </div>
  );
}

/** Single scene row with POV character + confidence badge. */
function SceneRow({ scene, t }: { scene: POVScene; t: (key: string) => string }) {
  const confidencePercent = Math.round(scene.confidence * 100);

  return (
    <div className="flex items-center gap-3 rounded-lg border border-border p-3 bg-background">
      <span className="text-xs text-muted-foreground flex-shrink-0">
        {t("pov.scene")} {scene.scene_index + 1}
      </span>
      <span className="text-sm font-medium truncate flex-1 min-w-0">
        {scene.pov_character ?? "—"}
      </span>
      <span
        className={`text-xs font-medium px-2 py-0.5 rounded flex-shrink-0 ${getConfidenceColorClass(scene.confidence)}`}
        title={`${t("pov.confidence")}: ${confidencePercent}%`}
      >
        {confidencePercent}%
      </span>
    </div>
  );
}

/** Expandable issue row. */
function IssueRow({
  issue,
  t,
}: {
  issue: POVIssue;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}) {
  const [expanded, setExpanded] = useState(false);

  const typeLabel: Record<POVIssue["type"], string> = {
    head_hop: t("pov.headHop"),
    knowledge_leak: t("pov.knowledgeLeak"),
    emotional_leak: t("pov.emotionalLeak"),
    physical_impossibility: t("pov.physicalImpossibility"),
  };

  return (
    <div className="rounded-lg border border-border p-3">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-start gap-2 text-left"
        aria-expanded={expanded}
      >
        <SeverityIcon severity={issue.severity} />
        <div className="flex-1 min-w-0 space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className={`text-xs font-medium px-2 py-0.5 rounded ${getIssueTypeBadgeClass(issue.type)}`}
            >
              {typeLabel[issue.type]}
            </span>
            <span className="text-xs text-muted-foreground">{issue.location}</span>
          </div>
          <p className="text-xs text-muted-foreground italic truncate">
            {t("pov.quotedExcerpt", { text: issue.text })}
          </p>
        </div>
        <span className="text-muted-foreground flex-shrink-0 mt-0.5">
          {expanded ? (
            <ChevronUp className="w-3.5 h-3.5" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5" />
          )}
        </span>
      </button>
      {expanded && (
        <div className="mt-3 ml-6 space-y-2 text-xs border-t border-border pt-2">
          <div>
            <span className="font-medium">{t("pov.explanation")}</span>
            <p className="text-muted-foreground mt-0.5">{issue.explanation}</p>
          </div>
          <div>
            <span className="font-medium">{t("pov.suggestion")}</span>
            <p className="text-muted-foreground mt-0.5">{issue.suggestion}</p>
          </div>
        </div>
      )}
    </div>
  );
}

// --- Component ---

export function POVPanel({ novelId, chapterIds, onClose }: POVPanelProps) {
  const t = useTranslations("analysis");

  const [viewState, setViewState] = useState<"idle" | "loading" | "results" | "error">("idle");
  const [result, setResult] = useState<POVResult | null>(null);
  const [error, setError] = useState<Error | null>(null);

  const analyzeMutation = usePOVAnalysis(novelId);

  // --- Run analysis ---

  const runAnalysis = useCallback(
    async (_refresh = false) => {
      if (chapterIds.length === 0) return;
      setViewState("loading");
      setError(null);

      try {
        const res = await analyzeMutation.mutateAsync({
          chapter_ids: chapterIds,
        });
        setResult(res);
        setViewState("results");
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
        setViewState("error");
      }
    },
    [chapterIds, analyzeMutation],
  );

  // Auto-trigger on mount
  // biome-ignore lint/correctness/useExhaustiveDependencies: Runs once on mount
  useEffect(() => {
    if (viewState !== "idle") return;
    void runAnalysis(false);
  }, []);

  // --- Derived ---

  const distributionEntries = result
    ? Object.entries(result.pov_distribution).sort(([, a], [, b]) => b - a)
    : [];

  // --- Render ---

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
            <Eye className="w-5 h-5 text-indigo-500 flex-shrink-0" />
            <h3 className="font-medium truncate">{t("pov.title")}</h3>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {viewState === "results" && (
            <button
              type="button"
              onClick={() => void runAnalysis(true)}
              disabled={analyzeMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-border rounded-md hover:bg-muted transition-colors disabled:opacity-50"
              aria-label={t("refresh")}
            >
              <RefreshCw
                className={`w-3.5 h-3.5 ${analyzeMutation.isPending ? "animate-spin" : ""}`}
              />
              {t("refresh")}
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-muted-foreground hover:text-foreground rounded-md hover:bg-muted transition-colors"
            aria-label={t("close")}
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Info banner */}
      <div className="px-4 py-1.5 border-b border-border bg-muted/30">
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Info className="w-3.5 h-3.5 flex-shrink-0" />
          {t("pov.description")}
        </p>
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto p-6 space-y-4">
          {/* Loading state */}
          {viewState === "loading" && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="relative mb-6">
                <div className="w-16 h-16 rounded-full bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center">
                  <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
                </div>
              </div>
              <p className="text-lg font-medium mb-2">{t("pov.analyzing")}</p>
            </div>
          )}

          {/* Error state */}
          {viewState === "error" && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="w-12 h-12 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center mb-4">
                <Info className="w-6 h-6 text-red-500" />
              </div>
              <p className="text-lg font-medium mb-1">{t("pov.analysisFailed")}</p>
              <p className="text-sm text-muted-foreground mb-4">{error?.message}</p>
              <button
                type="button"
                onClick={() => void runAnalysis(false)}
                className="flex items-center gap-1.5 px-4 py-2 text-sm border border-border rounded-md hover:bg-muted transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                {t("pov.retry")}
              </button>
            </div>
          )}

          {/* Results */}
          {viewState === "results" && result && (
            <>
              {/* Summary stats */}
              <section className="grid grid-cols-3 gap-2">
                <div className="rounded-lg border border-border p-3 bg-background text-center">
                  <div className="text-xs text-muted-foreground mb-1">{t("pov.analysisType")}</div>
                  <div className="text-sm font-medium capitalize">
                    {result.analysis_type.replace(/_/g, " ")}
                  </div>
                </div>
                <div className="rounded-lg border border-border p-3 bg-background text-center">
                  <div className="text-xs text-muted-foreground mb-1">{t("pov.switchCount")}</div>
                  <div className="text-sm font-medium">{result.switch_count}</div>
                </div>
                <div className="rounded-lg border border-border p-3 bg-background text-center">
                  <div className="text-xs text-muted-foreground mb-1">{t("pov.issues")}</div>
                  <div className="text-sm font-medium">{result.issues.length}</div>
                </div>
              </section>

              {/* POV Distribution */}
              {distributionEntries.length > 0 && (
                <section>
                  <h4 className="text-sm font-medium mb-3">{t("pov.distribution")}</h4>
                  <div className="space-y-2">
                    {distributionEntries.map(([character, percentage]) => (
                      <DistributionBar
                        key={`dist-${character}`}
                        character={character}
                        percentage={percentage}
                      />
                    ))}
                  </div>
                </section>
              )}

              {/* Scene Map */}
              {result.scenes.length > 0 && (
                <section>
                  <h4 className="text-sm font-medium mb-3">{t("pov.scenes")}</h4>
                  <div className="space-y-2">
                    {result.scenes.map((scene) => (
                      <SceneRow key={`scene-${scene.scene_index}`} scene={scene} t={t} />
                    ))}
                  </div>
                </section>
              )}

              {/* Issues */}
              <section>
                <h4 className="text-sm font-medium mb-2">
                  {result.issues.length > 0 ? t("pov.issues") : t("pov.noIssues")}
                </h4>
                {result.issues.length > 0 && (
                  <div className="space-y-2">
                    {result.issues.map((issue) => (
                      <IssueRow
                        key={`issue-${issue.type}-${issue.location}-${issue.text.slice(0, 30)}`}
                        issue={issue}
                        t={t}
                      />
                    ))}
                  </div>
                )}
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
