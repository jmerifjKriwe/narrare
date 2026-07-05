import { Search, X } from "lucide-react";
import { type ChangeEvent, useId } from "react";
import { IconButton } from "@/components/ui/icon-button";
import { cn } from "@/lib/utils";

interface SearchInputProps {
  /** Required accessible label (resolved i18n). Visible or screen-reader-only. */
  readonly label: string;
  /** Controlled search value. */
  readonly value: string;
  /** Called with the new value on every keystroke. */
  readonly onValueChange: (value: string) => void;
  /** Optional clear handler — renders a trailing IconButton when set and value is non-empty. */
  readonly onClear?: () => void;
  /** Resolved i18n label for the clear control (required when onClear is set). */
  readonly clearLabel?: string;
  /** Input placeholder (resolved i18n). */
  readonly placeholder?: string;
  /** Render the label visibly (default) or screen-reader-only. */
  readonly visibleLabel?: boolean;
}

/**
 * Labelled text search with a clear button and a URL-sync seam (spec §5.6).
 *
 * Presentation only — the caller wires `value`/`onValueChange` to
 * `useUrlParam` (one adapter per surface) or local state. The clear control
 * reuses IconButton. No hardcoded user-facing strings: `label` and
 * `clearLabel` are required resolved-i18n props (RULE-16).
 */
export function SearchInput({
  label,
  value,
  onValueChange,
  onClear,
  clearLabel,
  placeholder,
  visibleLabel = true,
}: SearchInputProps) {
  const id = useId();

  if (onClear && !clearLabel) {
    throw new Error("SearchInput: clearLabel is required when onClear is provided (RULE-16).");
  }

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => onValueChange(e.target.value);

  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor={id}
        className={cn("text-xs text-muted-foreground", !visibleLabel && "sr-only")}
      >
        {label}
      </label>
      <div className="relative">
        <Search
          aria-hidden="true"
          className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
        />
        <input
          id={id}
          type="search"
          value={value}
          onChange={handleChange}
          placeholder={placeholder}
          aria-label={label}
          className={cn(
            "w-full rounded-md border border-border bg-input-background py-1.5 pl-8 pr-8 text-sm text-foreground",
            "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
          )}
        />
        {onClear && value && (
          <span className="absolute right-1 top-1/2 -translate-y-1/2">
            <IconButton label={clearLabel as string} icon={X} onClick={onClear} size="sm" />
          </span>
        )}
      </div>
    </div>
  );
}
