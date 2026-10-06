"use client";

/**
 * CostsBreakdownTables — by-feature (intent) and by-model cost tables
 * (STATS-002, ADR-093 §5). Extracted from AnalyticsCostsPanel to keep it
 * under the RULE-04 limit.
 *
 * Intent labels come from `analytics.costs.intent.<intent>` via a dedicated
 * translator with a raw-key fallback (`t.has()`) until Task 15 lands the
 * messages; model cells show `provider / model_id` monospaced.
 */

import { useFormatter, useTranslations } from "next-intl";
import type { ReactNode } from "react";
import type { CostIntentRow, CostModelRow } from "@/lib/api/analytics";

interface CostsTableProps {
  label: string;
  firstHeader: string;
  rows: Array<{ key: string; first: ReactNode; calls: number; cost: string }>;
}

function CostsTable({ label, firstHeader, rows }: CostsTableProps) {
  const t = useTranslations("analytics.costs");
  return (
    <table className="w-full text-sm" aria-label={label}>
      <thead>
        <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
          <th className="py-1 pr-3">{firstHeader}</th>
          <th className="py-1 pr-3">{t("calls")}</th>
          <th className="py-1 pr-3">{t("cost")}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.key} className="border-t border-border">
            <td className="py-2 pr-3">{row.first}</td>
            <td className="py-2 pr-3 font-mono tabular-nums">{row.calls}</td>
            <td className="py-2 pr-3 font-mono tabular-nums">{row.cost}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

interface CostsBreakdownTablesProps {
  readonly byIntent: CostIntentRow[];
  readonly byModel: CostModelRow[];
}

export function CostsBreakdownTables({ byIntent, byModel }: CostsBreakdownTablesProps) {
  const t = useTranslations("analytics.costs");
  const tIntent = useTranslations("analytics.costs.intent");
  const format = useFormatter();
  const usd = (value: number) => format.number(value, { style: "currency", currency: "USD" });
  const intentLabel = (intent: string) => (tIntent.has(intent) ? tIntent(intent) : intent);

  return (
    <>
      <CostsTable
        label={t("byFeature")}
        firstHeader={t("feature")}
        rows={byIntent.map((row) => ({
          key: row.intent,
          first: intentLabel(row.intent),
          calls: row.calls,
          cost: usd(row.cost_usd),
        }))}
      />
      <CostsTable
        label={t("byModel")}
        firstHeader={t("model")}
        rows={byModel.map((row) => ({
          key: `${row.provider}/${row.model_id}`,
          first: (
            <span className="font-mono text-xs">
              {row.provider} / {row.model_id}
            </span>
          ),
          calls: row.calls,
          cost: usd(row.cost_usd),
        }))}
      />
    </>
  );
}
