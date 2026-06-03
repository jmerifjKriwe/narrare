/**
 * SentimentVadGauge — horizontal bar gauge for a single VAD dimension.
 *
 * Maps the -1..+1 scale to a 0–100% fill width.
 */

interface VadGaugeProps {
  label: string;
  value: number;
  color: string;
}

export function VadGauge({ label, value, color }: VadGaugeProps) {
  // Map -1..+1 to 0..100% for display
  const percentage = ((value + 1) / 2) * 100;

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className="text-xs font-medium">{value.toFixed(2)}</span>
      </div>
      <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
