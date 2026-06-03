/**
 * ReadabilityMetricCard — single metric display card for readability statistics.
 *
 * Shows a label-value pair in a bordered card, used in the statistics grid.
 */

interface MetricCardProps {
  label: string;
  value: string;
  unit?: string;
}

export function ReadabilityMetricCard({ label, value, unit }: MetricCardProps) {
  return (
    <div className="rounded-lg border border-border p-3 bg-background">
      <div className="text-xs text-muted-foreground mb-1">{label}</div>
      <div className="text-sm font-medium">
        {value}
        {unit && <span className="text-xs text-muted-foreground ml-1">{unit}</span>}
      </div>
    </div>
  );
}
