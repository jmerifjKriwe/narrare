"use client";

import { Switch } from "@/components/ui/switch";

/**
 * Shared labelled field primitives for the export options form.
 *
 * Extracted from ExportOptionsForm for RULE-04 file-size compliance.
 * ToggleRow follows the AdaptiveToggle pattern (div row + Switch with
 * aria-label) so the row is not a <label> without a native form control.
 */

interface ToggleRowProps {
  label: string;
  checked: boolean;
  disabled: boolean;
  onCheckedChange: (checked: boolean) => void;
}

/** A labelled toggle row (Switch + text). */
export function ToggleRow({ label, checked, disabled, onCheckedChange }: ToggleRowProps) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-sm text-foreground">{label}</span>
      <Switch
        checked={checked}
        disabled={disabled}
        onCheckedChange={onCheckedChange}
        aria-label={label}
      />
    </div>
  );
}

interface NumberFieldProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  disabled: boolean;
  onChange: (value: number) => void;
}

/** A labelled number field. */
export function NumberField({
  label,
  value,
  min,
  max,
  step,
  disabled,
  onChange,
}: NumberFieldProps) {
  return (
    <label className="flex items-center justify-between py-1.5">
      <span className="text-sm text-foreground">{label}</span>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-24 rounded-md border border-border bg-background px-2 py-1 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      />
    </label>
  );
}
