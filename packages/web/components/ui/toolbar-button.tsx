import { Loader2, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type ToolbarButtonVariant = "ghost" | "default" | "destructive";

interface ToolbarButtonProps {
  /** Required — visible label and/or accessible name (resolved i18n). */
  readonly label: string;
  readonly icon?: LucideIcon;
  readonly onClick?: () => void;
  readonly disabled?: boolean;
  readonly loading?: boolean;
  /** Show the visible label (wide) vs icon-only (narrow). Default false. */
  readonly showLabel?: boolean;
  readonly variant?: ToolbarButtonVariant;
  /** Pressed/toggle state (e.g. active formatting). Reflects aria-pressed. */
  readonly active?: boolean;
}

const VARIANT_CLASSES: Record<ToolbarButtonVariant, string> = {
  ghost: "text-foreground hover:bg-accent",
  default: "bg-primary text-primary-foreground hover:opacity-90",
  destructive: "text-destructive hover:bg-destructive/10 border border-destructive",
};

/**
 * Editor/panel toolbar action — a labelled, horizontally-grouped button set
 * (spec §5.5). Distinct from IconButton: supports a visible label and an
 * active/pressed state. Always type="button"; aria-pressed when active.
 * Presentation only — callers pass resolved i18n strings (RULE-16).
 */
export function ToolbarButton({
  label,
  icon: Icon,
  onClick,
  disabled = false,
  loading = false,
  showLabel = false,
  variant = "ghost",
  active = false,
}: ToolbarButtonProps) {
  const isDisabled = disabled || loading;
  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={active || undefined}
      aria-disabled={isDisabled || undefined}
      aria-busy={loading || undefined}
      disabled={isDisabled}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded px-2 py-1 text-sm transition-colors",
        "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
        active && "bg-accent",
        VARIANT_CLASSES[variant],
        isDisabled && "opacity-50",
      )}
    >
      {loading ? (
        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
      ) : (
        Icon && <Icon aria-hidden="true" className="h-4 w-4" />
      )}
      {showLabel && <span>{label}</span>}
    </button>
  );
}
