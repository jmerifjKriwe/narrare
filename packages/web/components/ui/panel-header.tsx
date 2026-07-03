import { type LucideIcon, X } from "lucide-react";
import { type ReactNode, useId } from "react";
import { IconButton } from "@/components/ui/icon-button";
import { cn } from "@/lib/utils";

interface PanelHeaderProps {
  /** Resolved i18n title string (required). */
  readonly title: string;
  readonly icon?: LucideIcon;
  readonly description?: string;
  /** Live status/progress slot — integration point for StatusMessage. */
  readonly statusSlot?: ReactNode;
  /** Trailing actions (refresh/stop). */
  readonly actions?: ReactNode;
  /** When provided, renders an IconButton close control and calls on close. */
  readonly onClose?: () => void;
  /** Resolved i18n label for the close control (required when onClose is set). */
  readonly closeLabel?: string;
  /** Optional explicit id for the title (lets PanelShell link aria-labelledby). */
  readonly titleId?: string;
}

/**
 * Accessible header for a workspace side panel / inspector (spec §5.2).
 * Presentation only (RULE-13). The title element carries a stable id so
 * PanelShell can wire aria-labelledby. Replaces the duplicated
 * `flex items-center justify-between p-4 border-b bg-card` + close boilerplate.
 */
export function PanelHeader({
  title,
  icon: Icon,
  description,
  statusSlot,
  actions,
  onClose,
  closeLabel,
  titleId,
}: PanelHeaderProps) {
  const generated = useId();
  const id = titleId ?? generated;

  if (onClose && !closeLabel) {
    throw new Error("PanelHeader: closeLabel is required when onClose is provided (RULE-16).");
  }

  return (
    <div
      className={cn("flex items-center justify-between gap-3 border-b border-border bg-card p-4")}
    >
      <div className="flex min-w-0 items-center gap-3">
        {Icon && <Icon aria-hidden="true" className="h-5 w-5 shrink-0 text-muted-foreground" />}
        <div className="min-w-0">
          <h3 id={id} className="truncate font-medium text-foreground">
            {title}
          </h3>
          {description && <p className="truncate text-xs text-muted-foreground">{description}</p>}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {statusSlot}
        {actions}
        {onClose && <IconButton label={closeLabel as string} icon={X} onClick={onClose} />}
      </div>
    </div>
  );
}
