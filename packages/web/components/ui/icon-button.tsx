import { Loader2, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type IconButtonVariant = "ghost" | "destructive" | "default";
type IconButtonSize = "sm" | "md";

interface IconButtonProps {
  /** Required accessible name (resolved i18n string). Becomes aria-label. */
  readonly label: string;
  /** Lucide icon component to render. */
  readonly icon: LucideIcon;
  /** Click handler. */
  readonly onClick?: () => void;
  /** Disables the button and reflects aria-disabled. */
  readonly disabled?: boolean;
  /** Shows a spinner, hides the icon, sets aria-busy. */
  readonly loading?: boolean;
  /** Visual variant. Defaults to "ghost". */
  readonly variant?: IconButtonVariant;
  /** Touch target size. Defaults to "md". */
  readonly size?: IconButtonSize;
  /** Additional CSS classes merged into the button (positioning, layout, etc.). */
  readonly className?: string;
  /** Optional data-testid for integration tests. */
  readonly "data-testid"?: string;
}

const VARIANT_CLASSES: Record<IconButtonVariant, string> = {
  ghost: "text-muted-foreground hover:bg-muted hover:text-foreground rounded-md",
  default: "bg-primary text-primary-foreground rounded-md hover:opacity-90",
  destructive: "text-destructive hover:bg-destructive/10 rounded-md border border-destructive",
};

const SIZE_CLASSES: Record<IconButtonSize, string> = {
  sm: "p-1",
  md: "p-1.5",
};

/**
 * Atomic icon-only action button. The accessible name is the required `label`
 * prop (a resolved i18n string) — never inferred. Always renders type="button".
 * Replaces the hand-rolled `<button type="button" aria-label=... className="p-1.5 ...">`
 * pattern (spec §1). a11y per ui-principles §11.
 */
export function IconButton({
  label,
  icon: Icon,
  onClick,
  disabled = false,
  loading = false,
  variant = "ghost",
  size = "md",
  className,
  ...rest
}: IconButtonProps) {
  const isDisabled = disabled || loading;
  return (
    <button
      type="button"
      aria-label={label}
      aria-disabled={isDisabled || undefined}
      aria-busy={loading || undefined}
      disabled={isDisabled}
      onClick={onClick}
      className={cn(
        "inline-flex items-center justify-center transition-colors",
        "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
        VARIANT_CLASSES[variant],
        SIZE_CLASSES[size],
        className,
      )}
      {...("data-testid" in rest ? { "data-testid": rest["data-testid"] } : {})}
    >
      {loading ? (
        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
      ) : (
        <Icon aria-hidden="true" className="h-4 w-4" />
      )}
    </button>
  );
}
