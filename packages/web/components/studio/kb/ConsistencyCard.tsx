"use client";

/**
 * ConsistencyCard — single KB consistency finding card.
 *
 * Shows severity, confidence, entity names, contradiction, and optional
 * suggested resolution. Carries dismiss/undismiss controls (CR-AUFG-07-26)
 * when the parent wires them; the fingerprint is computed locally via
 * consistencyFingerprint so callers receive a stable key.
 *
 * Extracted from WorldbuildingAnalysisCards for RULE-04 compliance.
 */

import { Eye, EyeOff } from "lucide-react";
import { IconButton } from "@/components/ui/icon-button";
import { consistencyFingerprint } from "@/lib/api/consistency";
import type { ConsistencyIssue } from "@/lib/api/worldbuilding";
import { SEVERITY_COLORS } from "./severityStyles";

interface ConsistencyCardProps {
  issue: ConsistencyIssue;
  t: (key: string) => string;
  onEntityClick?: (entityId: string) => void;
  /** Called with the issue fingerprint when the user dismisses the finding. */
  onDismiss?: (fingerprint: string) => void;
  /** Called with the issue fingerprint when the user restores a dismissed finding. */
  onUndismiss?: (fingerprint: string) => void;
  /** Whether this finding has been dismissed (shows badge + restore button). */
  dismissed?: boolean;
}

export function ConsistencyCard({
  issue,
  t,
  onEntityClick,
  onDismiss,
  onUndismiss,
  dismissed = false,
}: ConsistencyCardProps) {
  const fingerprint = consistencyFingerprint(issue);

  return (
    <div
      className={`border rounded-lg overflow-hidden transition-opacity ${
        dismissed ? "border-border opacity-60" : "border-border"
      }`}
    >
      <div className="flex items-center justify-between p-3 bg-muted/30">
        <div className="flex items-center gap-2">
          <span
            className={`text-xs px-2 py-0.5 rounded font-medium ${SEVERITY_COLORS[issue.severity] ?? SEVERITY_COLORS.info}`}
          >
            {issue.severity}
          </span>
          <span className="text-xs text-muted-foreground">
            {Math.round(issue.confidence * 100)}% {t("worldbuilding.confidence")}
          </span>
          {dismissed && (
            <span className="text-xs px-2 py-0.5 rounded font-medium bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400">
              {t("kb.dismissedBadge")}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5 flex-wrap justify-end">
          {issue.entity_names.map((name, i) => {
            const entityId = issue.entity_ids[i];
            if (onEntityClick && entityId) {
              return (
                <button
                  key={entityId}
                  type="button"
                  onClick={() => onEntityClick(entityId)}
                  className="text-xs text-primary hover:underline cursor-pointer"
                >
                  {name}
                </button>
              );
            }
            return (
              <span
                key={`${name}-${issue.finding_index}`}
                className="text-xs text-muted-foreground"
              >
                {name}
              </span>
            );
          })}
          {/* Dismiss / undismiss controls (CR-AUFG-07-26) */}
          {dismissed
            ? onUndismiss && (
                <IconButton
                  label={t("kb.undismiss")}
                  icon={Eye}
                  onClick={() => onUndismiss(fingerprint)}
                  size="sm"
                />
              )
            : onDismiss && (
                <IconButton
                  label={t("kb.dismissFinding")}
                  icon={EyeOff}
                  onClick={() => onDismiss(fingerprint)}
                  size="sm"
                />
              )}
        </div>
      </div>
      <div className="p-3 space-y-2">
        <p className="text-sm">{issue.description}</p>
        <div className="p-2 bg-muted/20 rounded text-sm text-muted-foreground">
          <span className="font-medium">{t("worldbuilding.contradiction")}:</span>{" "}
          {issue.contradiction}
        </div>
        {issue.suggested_resolution && (
          <div className="p-2 bg-green-50 dark:bg-green-950/20 rounded text-sm">
            <span className="font-medium text-green-700 dark:text-green-400">
              {t("worldbuilding.resolution")}:
            </span>{" "}
            <span className="text-green-600 dark:text-green-400">{issue.suggested_resolution}</span>
          </div>
        )}
      </div>
    </div>
  );
}
