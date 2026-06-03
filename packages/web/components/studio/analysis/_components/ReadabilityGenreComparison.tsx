/**
 * ReadabilityGenreComparison — compares actual score against a genre benchmark.
 *
 * Shows the difference (positive = green, negative = red) between the actual
 * readability score and the genre benchmark.
 */

interface GenreComparisonProps {
  label: string;
  benchmark: number;
  actual: number;
}

export function ReadabilityGenreComparison({ label, benchmark, actual }: GenreComparisonProps) {
  const diff = actual - benchmark;
  const isBetter = diff >= 0;

  return (
    <div className="flex items-center justify-between rounded-lg border border-border p-3 bg-background">
      <span className="text-xs text-muted-foreground">{label}</span>
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">{benchmark.toFixed(1)}</span>
        <span
          className={`text-xs font-medium ${isBetter ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}
        >
          {isBetter ? "+" : ""}
          {diff.toFixed(1)}
        </span>
      </div>
    </div>
  );
}
