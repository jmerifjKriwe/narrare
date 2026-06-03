import { Check, ChevronDown, ChevronUp, Copy, Lightbulb, MapPin, X } from "lucide-react";
import { useState } from "react";
import type { ConsistencyIssue } from "@/lib/api/analysis";
import {
  CHECK_TYPE_LABELS,
  CHECK_TYPE_STYLES,
  SEVERITY_BORDER,
  SEVERITY_DOT,
  SEVERITY_STYLES,
} from "./consistencyIssueConfig";

interface ConsistencyIssueCardProps {
  issue: ConsistencyIssue;
  t: (key: string) => string;
  isIntentional: boolean;
  isCopied: boolean;
  onDismiss: () => void;
  onMarkIntentional: () => void;
  onCopySuggestion: () => void;
}

export function ConsistencyIssueCard({
  issue,
  t,
  isIntentional,
  isCopied,
  onDismiss,
  onMarkIntentional,
  onCopySuggestion,
}: ConsistencyIssueCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className={`rounded-lg border border-border border-l-2 p-4 ${SEVERITY_BORDER[issue.severity]}`}
    >
      <div className="flex items-start gap-2 mb-2 flex-wrap">
        <span
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${SEVERITY_STYLES[issue.severity]}`}
        >
          <span className={`w-1.5 h-1.5 rounded-full ${SEVERITY_DOT[issue.severity]}`} />
          {t(`consistency.severity.${issue.severity}`)}
        </span>
        <span
          className={`px-2 py-0.5 rounded text-xs font-medium ${CHECK_TYPE_STYLES[issue.check_type]}`}
        >
          {CHECK_TYPE_LABELS[issue.check_type]}
        </span>
        {isIntentional && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700 dark:bg-green-950/30 dark:text-green-400">
            <Check className="w-3 h-3" />
            {t("consistency.intentional")}
          </span>
        )}
      </div>

      <p className="text-sm mb-2">{issue.description}</p>

      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
        aria-expanded={expanded}
      >
        {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        {expanded ? t("consistency.detailsHide") : t("consistency.detailsShow")}
      </button>

      {expanded && <ConsistencyIssueDetails issue={issue} t={t} />}

      <div className="flex items-center gap-1 mt-3 pt-3 border-t border-border">
        <button
          type="button"
          onClick={onDismiss}
          className="flex items-center gap-1 px-2 py-1 text-xs text-muted-foreground hover:text-foreground rounded hover:bg-muted transition-colors"
          aria-label={t("consistency.actions.dismiss")}
        >
          <X className="w-3 h-3" />
          {t("consistency.actions.dismiss")}
        </button>
        <button
          type="button"
          onClick={onMarkIntentional}
          className={`flex items-center gap-1 px-2 py-1 text-xs rounded transition-colors ${
            isIntentional
              ? "text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-950/20"
              : "text-muted-foreground hover:text-foreground hover:bg-muted"
          }`}
          aria-label={t("consistency.actions.markIntentional")}
        >
          <Check className="w-3 h-3" />
          {isIntentional ? t("consistency.intentional") : t("consistency.actions.markIntentional")}
        </button>
        {issue.suggestion && (
          <button
            type="button"
            onClick={onCopySuggestion}
            className="flex items-center gap-1 px-2 py-1 text-xs text-muted-foreground hover:text-foreground rounded hover:bg-muted transition-colors"
            aria-label={t("consistency.actions.copySuggestion")}
          >
            <Copy className="w-3 h-3" />
            {isCopied ? t("consistency.actions.copied") : t("consistency.actions.copySuggestion")}
          </button>
        )}
      </div>
    </div>
  );
}

function ConsistencyIssueDetails({
  issue,
  t,
}: {
  issue: ConsistencyIssue;
  t: (key: string) => string;
}) {
  return (
    <div className="mt-2 space-y-2 pl-2">
      {issue.locations.length > 0 && (
        <div>
          <div className="flex items-center gap-1 text-xs font-medium text-muted-foreground mb-1">
            <MapPin className="w-3 h-3" />
            {t("consistency.locations")}
          </div>
          <ul className="text-xs text-muted-foreground space-y-0.5">
            {issue.locations.map((loc) => (
              <li key={`loc-${loc.slice(0, 40)}`}>{loc}</li>
            ))}
          </ul>
        </div>
      )}

      {issue.conflicting_facts.length > 0 && (
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-1">
            {t("consistency.conflictingFacts")}
          </p>
          <ul className="text-xs text-muted-foreground space-y-0.5">
            {issue.conflicting_facts.map((fact) => (
              <li key={`fact-${fact.slice(0, 40)}`} className="pl-2 border-l border-muted">
                {fact}
              </li>
            ))}
          </ul>
        </div>
      )}

      {issue.suggestion && (
        <div className="p-2 rounded bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/50">
          <div className="flex items-center gap-1 text-xs font-medium text-amber-700 dark:text-amber-400 mb-1">
            <Lightbulb className="w-3 h-3" />
            {t("consistency.suggestion")}
          </div>
          <p className="text-xs text-amber-800 dark:text-amber-300">{issue.suggestion}</p>
        </div>
      )}
    </div>
  );
}
