/**
 * POVDistributionBar — horizontal bar showing a character's POV percentage.
 */

interface POVDistributionBarProps {
  character: string;
  percentage: number;
}

export function POVDistributionBar({ character, percentage }: POVDistributionBarProps) {
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
