"use client";

import { useTranslations } from "next-intl";
import { useCallback, useMemo } from "react";
import type { ContextTier } from "@/types";

// --- Static config ---

const TIERS: { key: ContextTier; color: string; labelKey: string }[] = [
  {
    key: "immediate",
    color: "#3b82f6",
    labelKey: "settings.ai.contextBudget.tierImmediate",
  },
  {
    key: "recent",
    color: "#22c55e",
    labelKey: "settings.ai.contextBudget.tierRecent",
  },
  {
    key: "kb_referenced",
    color: "#a855f7",
    labelKey: "settings.ai.contextBudget.tierKbReferenced",
  },
  {
    key: "kb_suggested",
    color: "#f59e0b",
    labelKey: "settings.ai.contextBudget.tierKbSuggested",
  },
  {
    key: "pinned",
    color: "#f43f5e",
    labelKey: "settings.ai.contextBudget.tierPinned",
  },
];

// --- SVG helpers ---

function polarToCartesian(cx: number, cy: number, r: number, angle: number) {
  const rad = ((angle - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function describeArc(
  cx: number,
  cy: number,
  r: number,
  startAngle: number,
  endAngle: number,
  pct: number,
): string {
  if (pct < 0.1) return "";
  const start = polarToCartesian(cx, cy, r, endAngle);
  const end = polarToCartesian(cx, cy, r, startAngle);
  const largeArcFlag = endAngle - startAngle > 180 ? 1 : 0;
  return `M ${cx} ${cy} L ${start.x} ${start.y} A ${r} ${r} 0 ${largeArcFlag} 0 ${end.x} ${end.y} Z`;
}

// --- Types ---

interface ContextBudgetProps {
  readonly percentages: Record<ContextTier, number>;
  readonly onChange: (percentages: Record<ContextTier, number>) => void;
  readonly disabled?: boolean;
}

// --- Component ---

export function ContextBudget({ percentages, onChange, disabled }: ContextBudgetProps) {
  const t = useTranslations("studio");

  const total = useMemo(
    () => TIERS.reduce((sum, tier) => sum + (percentages[tier.key] ?? 0), 0),
    [percentages],
  );

  const isValid = Math.abs(total - 100) < 0.1;

  const handleChange = useCallback(
    (tier: ContextTier, value: number) => {
      onChange({ ...percentages, [tier]: value });
    },
    [percentages, onChange],
  );

  // SVG Pie Chart segments
  const segments = useMemo(() => {
    let cumulative = 0;
    return TIERS.map((tier) => {
      const pct = percentages[tier.key] ?? 0;
      const startAngle = (cumulative / 100) * 360;
      cumulative += pct;
      const endAngle = (cumulative / 100) * 360;
      return { ...tier, pct, startAngle, endAngle };
    });
  }, [percentages]);

  return (
    <div className="space-y-6">
      {/* Pie Chart */}
      <div className="flex justify-center">
        <svg width="180" height="180" viewBox="0 0 180 180" aria-hidden="true">
          {segments.map(
            (seg) =>
              seg.pct >= 0.1 && (
                <path
                  key={seg.key}
                  d={describeArc(90, 90, 80, seg.startAngle, seg.endAngle, seg.pct)}
                  fill={seg.color}
                  stroke="var(--color-card, #1e1e2e)"
                  strokeWidth="2"
                />
              ),
          )}
        </svg>
      </div>

      {/* Legend + Sliders */}
      <div className="space-y-3">
        {TIERS.map((tier) => (
          <div key={tier.key} className="flex items-center gap-3">
            <div
              className="w-3 h-3 rounded-full shrink-0"
              style={{ backgroundColor: tier.color }}
            />
            <span className="text-sm w-28 truncate">{t(tier.labelKey)}</span>
            <input
              type="range"
              min={0}
              max={100}
              step={1}
              value={percentages[tier.key] ?? 0}
              onChange={(e) => handleChange(tier.key, Number(e.target.value))}
              disabled={disabled}
              className="flex-1 accent-foreground"
              aria-label={t(tier.labelKey)}
            />
            <span className="text-sm w-12 text-right tabular-nums">
              {Math.round(percentages[tier.key] ?? 0)}%
            </span>
          </div>
        ))}
      </div>

      {/* Validation */}
      <div className="text-sm text-center">
        {isValid ? (
          <span className="text-green-600">{"\u2713"} 100%</span>
        ) : (
          <span className="text-amber-600">
            {t("settings.ai.contextBudget.sumWarning", { total: total.toFixed(1) })}
          </span>
        )}
      </div>
    </div>
  );
}
